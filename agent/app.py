import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    AudioMessageContent,
    VideoMessageContent,
    StickerMessageContent,
)

from core.config import STORAGE_CONFIG, USER_PROFILE_CONFIG, MULTIMODAL_CONFIG

from graph.builder import build_graph
from storage import get_storage, close_storage
from memory import close_checkpointer
from profiles import init_facts_db, close_facts_db

from tools.transfer_human import TransferHumanTool

import core.line_bot as line_bot
import core.debounce as debounce
import core.multimodal as multimodal

# 載入環境變數 (.env)
load_dotenv()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

app = FastAPI()

# 設定 Line 的 Parser
parser = WebhookParser(LINE_CHANNEL_SECRET)

# 審計日誌（在 startup 事件中非同步初始化）
audit_storage = None

# 轉接真人表單工具（非文字訊息直接回覆用）
transfer_tool = TransferHumanTool({})
transfer_tool.setup()

@app.on_event("startup")
async def startup_event():
    global audit_storage
    audit_storage = await get_storage(STORAGE_CONFIG)
    if USER_PROFILE_CONFIG.get("facts_enabled", False):
        await init_facts_db(USER_PROFILE_CONFIG)
    langgraph_app = await build_graph()

    line_bot.init(LINE_CHANNEL_ACCESS_TOKEN)
    debounce.init(langgraph_app, audit_storage)
    await multimodal.init(MULTIMODAL_CONFIG, LINE_CHANNEL_ACCESS_TOKEN)

    asyncio.create_task(debounce.cleanup_stale_buffers())

@app.on_event("shutdown")
async def shutdown_event():
    await multimodal.close()
    await close_facts_db()
    await close_storage()
    await close_checkpointer()

async def _handle_media_message(
    user_id: str, reply_token: str, message_id: str, media_type: str
):
    """背景任務：下載媒體 → 存檔 → Flash-Lite 描述 → 注入 debounce buffer。"""
    try:
        description = await multimodal.process_media_message(
            message_id, media_type, user_id
        )
        media_label = {"image": "圖片", "audio": "音檔", "video": "影片"}.get(
            media_type, "媒體"
        )
        enriched_text = f"[使用者傳送了{media_label}，以下是內容描述]\n{description}"

        if audit_storage:
            try:
                await audit_storage.log_message(
                    user_id, "media_description", f"[{media_type}] {description}"
                )
            except Exception as e:
                print(f"[Audit] 記錄媒體描述失敗: {e}")

        debounce.add_message_to_buffer(user_id, reply_token, enriched_text)

    except Exception as e:
        print(f"[Media Handler Error] {media_type} 處理異常 (user={user_id}): {e}")
        fallback = multimodal.get_sticker_reply()  # 最後防線：友善回覆
        await line_bot.send_response(user_id, reply_token, fallback)


@app.post("/webhook")
async def line_webhook(request: Request):
    """接收 Line 官方傳來的 Webhook"""
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body_str = body.decode('utf-8')

    try:
        events = parser.parse(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check your channel secret.")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = event.source.user_id
        reply_token = event.reply_token

        # ── 貼圖 → 友善回覆，不進 LangGraph ──
        if isinstance(event.message, StickerMessageContent):
            sticker_reply = multimodal.get_sticker_reply()
            if audit_storage:
                try:
                    await audit_storage.log_message(user_id, "user_raw", "[貼圖]")
                    await audit_storage.log_message(user_id, "ai", sticker_reply)
                except Exception as e:
                    print(f"[Audit] 記錄失敗: {e}")
            await line_bot.send_response(user_id, reply_token, sticker_reply)
            continue

        # ── 圖片/音訊/影片 → 多模態前處理 → debounce buffer ──
        if isinstance(event.message, (ImageMessageContent, AudioMessageContent, VideoMessageContent)):
            media_type_map = {
                ImageMessageContent: "image",
                AudioMessageContent: "audio",
                VideoMessageContent: "video",
            }
            media_type = media_type_map[type(event.message)]
            message_id = event.message.id

            if audit_storage:
                try:
                    await audit_storage.log_message(user_id, "user_raw", f"[{media_type}:{message_id}]")
                except Exception as e:
                    print(f"[Audit] 記錄失敗: {e}")

            if multimodal.is_enabled():
                print(f"[收到{media_type}訊息] user={user_id}, msg_id={message_id}")
                await line_bot.show_loading(user_id)
                asyncio.create_task(
                    _handle_media_message(user_id, reply_token, message_id, media_type)
                )
                continue

            # multimodal disabled → 降級為轉接真人
            print(f"[收到{media_type}訊息] 多模態停用，轉接真人 user={user_id}")
            form_reply = await transfer_tool.generate_form(user_id)
            if audit_storage:
                try:
                    await audit_storage.log_message(user_id, "ai", form_reply)
                except Exception as e:
                    print(f"[Audit] 記錄失敗: {e}")
            await line_bot.send_response(user_id, reply_token, form_reply)
            continue

        # ── 其他非文字訊息 (檔案、位置等) → 轉接真人 ──
        if not isinstance(event.message, TextMessageContent):
            print(f"[收到非文字訊息] user={user_id}")
            form_reply = await transfer_tool.generate_form(user_id)
            if audit_storage:
                try:
                    await audit_storage.log_message(user_id, "user_raw", "[非文字訊息]")
                    await audit_storage.log_message(user_id, "ai", form_reply)
                except Exception as e:
                    print(f"[Audit] 記錄失敗: {e}")
            await line_bot.send_response(user_id, reply_token, form_reply)
            continue

        # 以下為文字訊息處理流程
        new_text = event.message.text
        new_token = reply_token

        print(f"[收到訊息] '{new_text}' (Token: {new_token})")

        # 審計日誌：即時記錄使用者原始訊息（debounce 之前）
        if audit_storage:
            try:
                await audit_storage.log_message(user_id, "user_raw", new_text)
            except Exception as e:
                print(f"[Audit] 記錄原始訊息失敗: {e}")

        await line_bot.show_loading(user_id)
        debounce.add_message_to_buffer(user_id, new_token, new_text)

    return "OK"
