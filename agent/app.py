"""LINE 客服機器人 — skill-based ReAct agent + debounce + multimodal。

啟動：cd agent_skills && uvicorn app:app --reload --port 8000
所有設定從 config.toml 讀取。
"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

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

from core.config import load_config
from llms import get_llm
from memory import get_checkpointer, close_checkpointer
from profiles import ProfileManager, init_facts_db, close_facts_db
from storage import get_storage, close_storage
from agent import build_agent

import core.line_bot as line_bot
import harness.debounce as debounce
import harness.multimodal as multimodal
import harness.memory_manager as memory_manager
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate
import harness.output_validator as output_validator

app = FastAPI(title="Smart Lock AI Agent — Skill-Based")

# ── Global state ──
_cfg = None


def _get_env(env_name: str) -> str:
    """從 config 指定的 env var name 取值。"""
    return os.getenv(env_name, "")


# ── FastAPI lifecycle ──


@app.on_event("startup")
async def startup():
    global _cfg

    # 載入設定
    _cfg = load_config()
    print(f"[*] config loaded: domain={_cfg.system.get('domain', '')[:30]}...")

    # 建立 LLM（透過 registry）
    model = get_llm(_cfg.llm)

    # 建立 checkpointer（透過 registry）
    checkpointer = await get_checkpointer(_cfg.memory)

    # 建立 ProfileManager
    profile_mgr = ProfileManager(_cfg.user_profile)
    if _cfg.user_profile.get("facts_enabled", False):
        await init_facts_db(_cfg.user_profile)

    # 初始化用戶輪廓萃取器
    profile_updater.init(model, {
        **_cfg.user_profile,
        "domain": _cfg.system.get("domain", "電子鎖、智慧門鎖"),
        "update_profile_prompt": _cfg.prompts.get("update_profile_prompt", "prompts/update_profile.md"),
    }, profile_mgr)

    # 建立 agent
    agent = build_agent(model, _cfg, checkpointer=checkpointer, profile_mgr=profile_mgr)

    # 初始化 LINE Bot SDK
    line_cfg = _cfg.line_bot
    access_token = _get_env(line_cfg.get("channel_access_token_env", "LINE_CHANNEL_ACCESS_TOKEN"))
    line_bot.init(access_token, {
        "loading_seconds": line_cfg.get("loading_seconds", 20),
        "push_fallback_prefix": _cfg.templates.get("push_fallback_prefix", ""),
    })

    # 初始化記憶壓縮（使用 Flash 模型加速摘要）
    memory_llm = get_llm({
        "model": _cfg.memory.get("llm_model", "vertex_ai/gemini-2.5-flash"),
        "temperature": 0.2,
    })
    memory_manager.init(memory_llm, {
        **_cfg.memory,
        "domain": _cfg.system.get("domain", "電子鎖、智慧門鎖"),
        "summarize_prompt": _cfg.prompts.get("summarize_prompt", "prompts/summarize_messages.md"),
    }, profile_mgr=profile_mgr)

    # 初始化審計日誌
    audit_storage = await get_storage(_cfg.storage)

    # 初始化安全閘門 (H6)
    safety_gate.init(_cfg.safety)

    # 初始化輸出驗證器 (H7.5)
    output_validator.init(model, _cfg.output_validator)

    # 初始化 Quick Reply 快速回覆
    from harness.line_ui_factory import init_quick_reply
    init_quick_reply(_cfg.quick_reply)

    # 初始化 OPIK tracing
    opik_tracer = None
    if _cfg.opik.get("enabled", False):
        try:
            import opik
            api_key = _get_env(_cfg.opik.get("api_key_env", "OPIK_API_KEY"))
            opik.configure(
                api_key=api_key,
                workspace=_cfg.opik.get("workspace", "") or None,
                project_name=_cfg.opik.get("project_name", "smart-lock-agent"),
                force=True,
            )
            from opik.integrations.langchain import OpikTracer
            opik_tracer = OpikTracer(
                project_name=_cfg.opik.get("project_name", "smart-lock-agent"),
                tags=["production"],
            )
            print(f"[*] OPIK tracing enabled (project={_cfg.opik.get('project_name')})")
        except Exception as e:
            print(f"[*] OPIK init failed, tracing disabled: {e}")

    # 初始化 debounce (H3)
    debounce_config = {
        **_cfg.debounce,
        "request_timeout": _cfg.system.get("request_timeout", 60),
        "max_reply_length": line_cfg.get("max_reply_length", 5000),
    }
    debounce.init(agent, debounce_config, _cfg.templates, profile_mgr=profile_mgr, audit_storage=audit_storage, opik_tracer=opik_tracer)

    # 初始化 multimodal (H2)
    await multimodal.init(_cfg.multimodal, access_token)

    # 啟動背景清理任務
    asyncio.create_task(debounce.cleanup_stale_buffers())

    print("[*] Agent ready (skill-based + debounce + multimodal + audit)")


@app.on_event("shutdown")
async def shutdown():
    await multimodal.close()
    await close_storage()
    await close_checkpointer()
    await close_facts_db()
    print("[*] Connections closed")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0-skills"}


@app.get("/chat")
async def chat_test(q: str = "你好"):
    """GET /chat?q=門打不開 — 快速測試用（不經 debounce）。"""
    answer = await debounce.run_agent("test-cli", q)
    return {"answer": answer}


# ── LINE Webhook ──


@app.post("/webhook")
async def line_webhook(request: Request):
    """LINE Official Webhook Handler — 四路訊息處理。"""
    body = await request.body()
    body_str = body.decode("utf-8")
    signature = request.headers.get("X-Line-Signature", "")

    line_cfg = _cfg.line_bot
    secret = _get_env(line_cfg.get("channel_secret_env", "LINE_CHANNEL_SECRET"))

    parser = WebhookParser(secret)
    try:
        events = parser.parse(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=403, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = event.source.user_id
        reply_token = event.reply_token

        # ── 1. 貼圖 → 友善回覆 ──
        if isinstance(event.message, StickerMessageContent):
            sticker_reply = multimodal.get_sticker_reply()
            await line_bot.send_response(user_id, reply_token, sticker_reply)
            continue

        # ── 2. 圖片/音訊/影片 → 多模態 passthrough → debounce buffer ──
        if isinstance(event.message, (ImageMessageContent, AudioMessageContent, VideoMessageContent)):
            media_type_map = {
                ImageMessageContent: "image",
                AudioMessageContent: "audio",
                VideoMessageContent: "video",
            }
            media_type = media_type_map[type(event.message)]
            message_id = event.message.id

            if multimodal.is_enabled():
                print(f"[收到{media_type}訊息] user={user_id}, msg_id={message_id}")
                await line_bot.show_loading(user_id)
                # 先佔位，防止先前的文字 debounce 先觸發
                media_label = {"image": "圖片", "audio": "音檔", "video": "影片"}.get(media_type, "媒體")
                debounce.add_message_to_buffer(
                    user_id, reply_token,
                    {"type": "media_pending", "label": media_label}
                )
                # 背景處理：下載存檔後替換 buffer 中的佔位
                asyncio.create_task(
                    _handle_media_message(user_id, message_id, media_type)
                )
                continue

            # multimodal disabled → 提示僅支援文字
            await line_bot.send_response(
                user_id, reply_token,
                "目前僅支援文字訊息，請用文字描述您的問題。"
            )
            continue

        # ── 3. 文字 → debounce buffer ──
        if isinstance(event.message, TextMessageContent):
            text = event.message.text.strip()
            if not text:
                continue

            print(f"[LINE] user={user_id[:8]}... text={text[:50]}")
            await line_bot.show_loading(user_id)
            debounce.add_message_to_buffer(user_id, reply_token, text)
            continue

        # ── 4. 其他非文字訊息 ──
        await line_bot.send_response(
            user_id, reply_token,
            "目前僅支援文字與圖片訊息，請用文字描述您的問題。"
        )

    return {"status": "ok"}


async def _handle_media_message(user_id: str, message_id: str, media_type: str):
    """背景任務：下載媒體 → 存檔 → 注入 debounce buffer（passthrough，不做描述）。"""
    media_label = {"image": "圖片", "audio": "音檔", "video": "影片"}.get(media_type, "媒體")
    try:
        media_content = await multimodal.download_and_store_media(message_id, media_type, user_id)
        debounce.add_message_to_buffer(
            user_id, None, media_content, replace_media_pending=True
        )
    except Exception as e:
        print(f"[Media Handler Error] {media_type} 處理異常 (user={user_id}): {e}")
        debounce.add_message_to_buffer(
            user_id, None,
            f"[使用者傳送了{media_label}，但系統無法下載內容，請根據對話脈絡盡量協助]",
            replace_media_pending=True,
        )
