"""LINE 通道 — webhook 接入,把 LINE 訊息接到 LockCore AgentLoop。

流程:
  LINE 平台 --POST /callback--> 本服務(驗 X-Line-Signature)
    → 取 event.source.user_id(當 user_id)+ 文字
    → resolve_identity → (tenant, user_id)
    → AgentLoop._process_message → 回覆文字
    → LINE reply API 回給客人

身分:user_id 直接用 LINE 的 userId(per official-account 穩定);tenant 先固定單一店家。
機密(channel secret / access token)走 .env,不入庫。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from lockcore.bus.events import InboundMessage

# LINE 單則文字訊息上限 5000 字,留點 buffer。
_LINE_TEXT_LIMIT = 4900

# 內部錯誤外洩防線:LiteLLMProvider 失敗時 content 會是 "[litellm error] ..."。
# 這類字串(或空回覆)絕不可原文丟給客人,改回友善話術。
_ERROR_SENTINEL = "[litellm error]"
_FALLBACK_REPLY = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"

# 方案 A:對話旁路持久化。把每輪「客人訊息 + AI 回覆」POST 給 API,寫進
# conversations/messages,使工單/對話後台能重新渲染對話歷史。env 未設 → 略過
# (不破壞無此設定的既有部署);失敗一律 fail-soft(只 log,絕不阻斷回客人)。
#
# 逾時分兩種：
# - persist POST 在「回覆送出後」fire-and-forget，拉長到 20s 以撐過 API 冷啟動
#   （Cloud Run min-instances=0 時冷啟 ~10s），不影響客人回覆延遲。
# - handover 查詢在「回覆前」會阻塞回覆，維持短逾時 + fail-soft（查不到就 AI 照常回），
#   避免冷啟動拖慢客人首次回覆。
_PERSIST_TIMEOUT_SEC = 20.0
_HANDOVER_CHECK_TIMEOUT_SEC = 5.0


async def _persist_turn_safe(
    tenant: str, user_id: str, user_text: str, assistant_text: str
) -> None:
    """Fire-and-forget 旁路持久化一輪對話到 API。任何失敗只 log,不 raise。"""
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token):
        return  # 未設定 bridge → 安靜略過
    payload = {
        "tenant_id": tenant,
        "line_user_id": user_id,
        "session_id": f"{tenant}:{user_id}",
        "user_text": user_text or "",
        "assistant_text": assistant_text or "",
    }
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/conversations/ingest",
                json=payload,
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "對話持久化回 {}:{}", resp.status_code, resp.text[:160]
                )
    except Exception as e:  # noqa: BLE001 — 持久化絕不可影響客服回覆
        logger.warning("對話持久化失敗(已略過,不影響客人): {!r}", e)


async def _handover_active_safe(tenant: str, user_id: str) -> bool:
    """查該對話是否處於人工接管中（CR-0024 Phase 1）。escalated → True 表 AI 應暫停。

    **fail-soft**：bridge env 未設、查不到、逾時或任何錯誤 → 回 False（AI 照常回，
    絕不因為查詢失敗就把客人晾著）。Phase 1 只看 escalated 旗標（全暫停）。
    """
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token):
        return False
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_HANDOVER_CHECK_TIMEOUT_SEC) as client:
            resp = await client.get(
                f"{base_url.rstrip('/')}/api/v1/internal/conversations/handover-state",
                params={"tenant_id": tenant, "session_id": f"{tenant}:{user_id}"},
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning("查接管狀態回 {}:{}", resp.status_code, resp.text[:160])
                return False
            return bool(resp.json().get("data", {}).get("escalated", False))
    except Exception as e:  # noqa: BLE001 — 查詢失敗不可阻斷客人，預設 AI 照常回
        logger.warning("查接管狀態失敗（已略過，AI 照常回）: {!r}", e)
        return False


def _latest_escalation_id(esc: Any, tenant: str, user_id: str) -> int:
    """取該 user 最新 escalation id(無則 0)。用來偵測本輪是否新增轉真人紀錄。"""
    if esc is None:
        return 0
    try:
        recs = esc.list_for_user(tenant, user_id, limit=1)
        return recs[0].id if recs else 0
    except Exception:  # noqa: BLE001
        return 0


async def _forward_escalation_safe(esc: Any, tenant: str, user_id: str, before_id: int) -> None:
    """CR-0022:若本輪 agent 觸發了 transfer_to_human(escalation 變新),旁路 POST 給 API
    建 AI 草擬問題卡。env 未設 → 略過;失敗 fail-soft(只 log,不影響客人)。

    **AI 不自轉工單**:這裡只送 escalation,API 端最多建 draft PC;confirm/convert 走客服。
    """
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token) or esc is None:
        return
    try:
        recs = esc.list_for_user(tenant, user_id, limit=1)
    except Exception:  # noqa: BLE001
        return
    if not recs or recs[0].id <= before_id:
        return  # 本輪沒有新 escalation
    rec = recs[0]
    payload = {
        "tenant_id": tenant,
        "line_user_id": user_id,
        "session_id": f"{tenant}:{user_id}",
        "reason": rec.reason or "",
        "is_explicit": bool(rec.is_explicit),
        "facts_snapshot": rec.facts_snapshot or {},
    }
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/escalations/ingest",
                json=payload,
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning("escalation 轉發回 {}:{}", resp.status_code, resp.text[:160])
    except Exception:  # noqa: BLE001 — 轉發絕不可影響客服回覆
        logger.warning("escalation 轉發失敗(已略過,不影響客人)", exc_info=True)


def load_dotenv(path: str | Path) -> dict[str, str]:
    """極簡 .env 載入器(無外部依賴):把 KEY="value" 設進 os.environ(不覆蓋既有)。"""
    p = Path(path)
    loaded: dict[str, str] = {}
    if not p.exists():
        return loaded
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            loaded[key] = val
            os.environ.setdefault(key, val)
    return loaded


def resolve_identity(channel: str, native_id: str, tenant: str) -> tuple[str, str]:
    """把通道原生身分映射成 (tenant, user_id)。

    LINE:user_id 直接用 LINE 的 userId。tenant 目前固定傳入值(單一店家);
    日後多租戶可在此依「哪個官方帳號收到」反推 tenant。
    """
    return tenant, native_id


async def handle_text_turn(loop: Any, tenant: str, user_id: str, text: str) -> str:
    """跑一輪客服 turn,回傳要回給客人的文字('' = 不回)。"""
    if not (text or "").strip():
        return ""
    msg = InboundMessage(channel="line", sender_id=user_id, chat_id=user_id, content=text)
    out = await loop._process_message(msg, session_key=f"{tenant}:{user_id}")
    content = (getattr(out, "content", None) or "") if out is not None else ""
    if not content.strip():
        return ""
    if _ERROR_SENTINEL in content:
        logger.warning("LLM/provider 內部錯誤,改回友善訊息(不外洩):{}", content[:160])
        return _FALLBACK_REPLY
    return content[:_LINE_TEXT_LIMIT]


def build_webapp(
    loop: Any,
    tenant: str,
    channel_secret: str,
    channel_access_token: str,
    escalation_store: Any = None,
):
    """組 aiohttp app:POST /callback 收 LINE webhook。需要 line-bot-sdk(extra: line)。

    escalation_store:傳入則 CR-0022 啟用 —— 本輪 agent 轉真人時旁路建 AI 草擬問題卡。
    """
    from aiohttp import web
    from linebot.v3 import WebhookParser
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.messaging import (
        AsyncApiClient,
        AsyncMessagingApi,
        Configuration,
        ReplyMessageRequest,
        TextMessage,
    )
    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    parser = WebhookParser(channel_secret)
    config = Configuration(access_token=channel_access_token)

    async def callback(request):
        signature = request.headers.get("X-Line-Signature", "")
        body = await request.text()
        try:
            events = parser.parse(body, signature)
        except InvalidSignatureError:
            logger.warning("LINE webhook 簽章驗證失敗,拒絕")
            return web.Response(status=400, text="invalid signature")

        async with AsyncApiClient(config) as api_client:
            line_api = AsyncMessagingApi(api_client)
            for event in events:
                if not isinstance(event, MessageEvent):
                    continue
                if not isinstance(event.message, TextMessageContent):
                    continue
                native_id = getattr(event.source, "user_id", None)
                if not native_id:
                    continue
                _, user_id = resolve_identity("line", native_id, tenant)
                user_text = event.message.text

                # CR-0024 Phase 1:對話處於人工接管中 → AI 全暫停(不跑 turn、不回覆),
                # 只把客人這句旁路持久化讓客服在對話管理看得到;由真人回覆。
                # 交還(對話管理按鈕 / 工單結案)把對話翻回 active 後,AI 自動恢復。
                if await _handover_active_safe(tenant, user_id):
                    logger.info("對話接管中,AI 暫停回覆 user={}", user_id[:8])
                    await _persist_turn_safe(tenant, user_id, user_text, "")
                    continue

                # CR-0022:記本輪前的最新 escalation id,turn 後比對是否新增(觸發轉真人)。
                esc_before = _latest_escalation_id(escalation_store, tenant, user_id)
                try:
                    reply = await handle_text_turn(loop, tenant, user_id, user_text)
                except Exception:
                    logger.exception("LINE turn 失敗")
                    reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
                if reply:
                    await line_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)],
                        )
                    )
                # 回覆送出後再旁路(不影響客人回覆延遲;皆 fail-soft):
                # (1) 方案 A 對話持久化 (2) CR-0022 若本輪轉真人 → 建 AI 草擬問題卡。
                await _persist_turn_safe(tenant, user_id, user_text, reply)
                await _forward_escalation_safe(escalation_store, tenant, user_id, esc_before)
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post("/callback", callback)
    return app
