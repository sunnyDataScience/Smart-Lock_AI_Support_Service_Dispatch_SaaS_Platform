"""LINE Webhook router — CR-0017 Stage 4 (postback → service)。

收 LINE Platform 的 webhook callback，當前只處理 `postback` events：

  postback.data 短碼格式（與 templates/line_flex/builders.py 對齊）：
    - "r:c|<proposal_id>|<slot_idx>" — reschedule confirm
    - "r:r|<proposal_id>"             — reschedule reject
    - "s:a|<scope_change_id>"         — scope_change accept
    - "s:r|<scope_change_id>"         — scope_change reject

簽章驗證：x-line-signature header 用 LINE_CHANNEL_SECRET 做 HMAC-SHA256
然後 base64，與 request body 比對。簽章錯回 401。

注意：webhook 是 LINE 主動 POST，無需業務認證；簽章本身就是來源驗證。
回應一律 200（或 202）— LINE 失敗會 retry，重複 postback 由 service 端
CAS（CR-0017 Stage 4 wrapper）保證冪等。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from services import line_binding_service, scope_change_service, work_order_service

logger = logging.getLogger("api.line_webhook")

router = APIRouter()


def _verify_signature(body_bytes: bytes, signature: str | None) -> bool:
    """LINE x-line-signature 驗證。LINE_CHANNEL_SECRET 缺時 dev 模式略過。"""
    secret = os.getenv("LINE_CHANNEL_SECRET")
    if not secret:
        logger.warning("LINE_CHANNEL_SECRET missing — skip signature verify (DEV ONLY)")
        return True
    if not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


async def _push_text(line_uid: str, text: str) -> None:
    """簡易 LINE push text helper（postback handler 內部用）。
    失敗只 log 不 raise — postback 失敗不阻斷 webhook ack。
    """
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not access_token:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN missing, skip push")
        return
    try:
        from linebot.v3.messaging import (
            AsyncApiClient, AsyncMessagingApi, Configuration,
            PushMessageRequest, TextMessage,
        )
        cfg = Configuration(access_token=access_token)
        async with AsyncApiClient(cfg) as api_client:
            api = AsyncMessagingApi(api_client)
            await api.push_message(
                PushMessageRequest(
                    to=line_uid,
                    messages=[TextMessage(text=text[:5000])],
                ),
            )
    except Exception:  # noqa: BLE001
        logger.exception("_push_text failed line=%s", line_uid[:8])


# CR-0013 Stage 2: 預設 tenant id（無 multi-tenant lookup hint 時 fallback）
_DEFAULT_TENANT_FOR_LINE_LOOKUP = os.getenv(
    "LINE_DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001",
)
# CR-0013 Stage 2: web binding consume 頁面 base url
_WEB_BASE_URL_FOR_BINDING = os.getenv(
    "WEB_BASE_URL", "https://lock-ai-web.example.com",
)


async def _handle_get_progress(*, line_uid: str) -> None:
    """rich menu「查進度」postback：line_uid → user → active wo list → push。

    Multi-tenant 處理：先用 default tenant 查 binding，找不到再 fallback
    users.line_user_id（同 service.resolve_user_by_line_uid）。
    """
    user_id = await line_binding_service.resolve_user_by_line_uid(
        tenant_id=_DEFAULT_TENANT_FOR_LINE_LOOKUP, line_user_id=line_uid,
    )
    if not user_id:
        await _push_text(
            line_uid,
            "尚未綁定客戶資料。請先點選「綁定」選單完成綁定後再查詢進度。",
        )
        return
    # 簡化：發提示文字 + 客戶後續可在 web 看完整 list
    await _push_text(
        line_uid,
        f"查詢您的工單進度：{_WEB_BASE_URL_FOR_BINDING}/track/orders\n"
        "（含目前所有未完工工單）",
    )


async def _handle_binding_start(*, line_uid: str) -> None:
    """rich menu「綁定」postback：推 reply 含 web 端表單連結。

    流程：
      1. 客戶點 web 連結 → 看到 wo 詳情頁 + 「綁定 LINE 接收通知」鈕
      2. web 後端呼 generate_link_token 拿 token
      3. web 跳 LINE LIFF or 自家 form 帶 token + line_user_id 呼
         POST /api/v1/consumer/bindings:consume

    本函式只負責 push 訊息引導，不直接產 token（避免無 user_id 先 INSERT
    無對應的孤兒 row）。
    """
    await _push_text(
        line_uid,
        "綁定 LINE 接收工單通知\n"
        f"請開啟 web 端 {_WEB_BASE_URL_FOR_BINDING}/track/binding-start\n"
        "登入後點「綁定」即可。完成後您將自動收到工單派工、改期等通知。",
    )


async def _handle_postback(event: dict[str, Any]) -> None:
    """單一 postback event → dispatch 到對應 service。"""
    data = (event.get("postback") or {}).get("data") or ""
    source = event.get("source") or {}
    line_uid = source.get("userId") or "?"

    parts = data.split("|")
    if not parts:
        logger.warning("postback data malformed: %s", data)
        return

    kind = parts[0]
    try:
        if kind == "g:p" and len(parts) == 1:
            # CR-0013 Stage 2: 「查進度」rich menu postback
            await _handle_get_progress(line_uid=line_uid)
            logger.info("postback get progress: line=%s", line_uid[:8])
        elif kind == "b:s" and len(parts) == 1:
            # CR-0013 Stage 2: 「綁定」rich menu postback —
            # 啟動 binding 流程，回 reply 含 web link
            await _handle_binding_start(line_uid=line_uid)
            logger.info("postback binding start: line=%s", line_uid[:8])
        elif kind == "r:c" and len(parts) == 3:
            proposal_id, slot_idx_str = parts[1], parts[2]
            slot_idx = int(slot_idx_str)
            await work_order_service.confirm_reschedule_by_proposal(
                proposal_id=proposal_id, slot_idx=slot_idx,
            )
            logger.info(
                "postback reschedule confirm: proposal=%s slot=%d line=%s",
                proposal_id[:8], slot_idx, line_uid[:8],
            )
        elif kind == "r:r" and len(parts) == 2:
            proposal_id = parts[1]
            await work_order_service.reject_reschedule_by_proposal(
                proposal_id=proposal_id,
            )
            logger.info(
                "postback reschedule reject: proposal=%s line=%s",
                proposal_id[:8], line_uid[:8],
            )
        elif kind == "s:a" and len(parts) == 2:
            sc_id = parts[1]
            await scope_change_service.respond_public(
                proposal_id=sc_id, decision="accept",
            )
            logger.info(
                "postback scope_change accept: sc=%s line=%s",
                sc_id[:8], line_uid[:8],
            )
        elif kind == "s:r" and len(parts) == 2:
            sc_id = parts[1]
            await scope_change_service.respond_public(
                proposal_id=sc_id, decision="reject",
            )
            logger.info(
                "postback scope_change reject: sc=%s line=%s",
                sc_id[:8], line_uid[:8],
            )
        else:
            logger.warning("unknown postback kind: %s (full: %s)", kind, data)
    except Exception:  # noqa: BLE001
        # CR-0017: postback 失敗不阻斷其他事件；LINE 不會 retry HTTP 200
        # 重複 postback 由 service CAS 保證冪等
        logger.exception(
            "postback handler failed: kind=%s data=%s", kind, data,
        )


@router.post("/line/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None, alias="X-Line-Signature"),
) -> dict:
    """LINE Platform webhook 入口（CR-0017 Stage 4）。"""
    body_bytes = await request.body()

    if not _verify_signature(body_bytes, x_line_signature):
        logger.warning("invalid LINE signature, rejecting")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        body = json.loads(body_bytes.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    events = body.get("events") or []
    for event in events:
        evt_type = event.get("type")
        if evt_type == "postback":
            await _handle_postback(event)
        # 其他 event type（message/follow/unfollow）由 agent gateway 處理；
        # 本 router 專責 CR-0017 postback。
    return {"ok": True, "processed": len(events)}
