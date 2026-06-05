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

from services import scope_change_service, work_order_service

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


async def _handle_postback(event: dict[str, Any]) -> None:
    """單一 postback event → dispatch 到對應 service。"""
    data = (event.get("postback") or {}).get("data") or ""
    source = event.get("source") or {}
    line_uid = source.get("userId") or "?"

    parts = data.split("|")
    if not parts or len(parts) < 2:
        logger.warning("postback data malformed: %s", data)
        return

    kind = parts[0]
    try:
        if kind == "r:c" and len(parts) == 3:
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
