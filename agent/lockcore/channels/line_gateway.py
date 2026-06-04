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


def build_webapp(loop: Any, tenant: str, channel_secret: str, channel_access_token: str):
    """組 aiohttp app:POST /callback 收 LINE webhook。需要 line-bot-sdk(extra: line)。"""
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
                try:
                    reply = await handle_text_turn(loop, tenant, user_id, event.message.text)
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
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post("/callback", callback)
    return app
