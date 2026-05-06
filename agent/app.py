"""LINE 客服機器人 — skill-based ReAct agent + debounce + multimodal。

啟動：cd agent_skills && uvicorn app:app --reload --port 8000
所有設定從 config.toml 讀取。
"""

import os
import asyncio
import logging
import warnings

# 抑制 OPIK 序列化 LangChain Run 物件時的 Pydantic v2 警告
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
)

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
from core.tracing import configure_tracing, instrument_fastapi
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
import harness.data_correction as data_correction

app = FastAPI(title="Smart Lock AI Agent — Skill-Based")

# ── OpenTelemetry：須在 FastAPI 建立後、first request 前 instrument ──
# 預設 ConsoleSpanExporter（本機 stdout）；設 OTEL_EXPORTER_OTLP_ENDPOINT 即切 OTLP
configure_tracing(service_name="smart-lock-agent")
instrument_fastapi(app)

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

    # 初始化記憶壓縮（摘要任務不需深度推理 → 低 thinking_budget）
    memory_llm = get_llm({
        "model": _cfg.memory.get("llm_model", "vertex_ai/gemini-2.5-flash"),
        "temperature": 0.2,
        "thinking_budget": 256,
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

    # 初始化資料修正攔截
    await data_correction.init_db(_cfg.data_correction)

    # 初始化 OPIK tracing
    opik_tracer = None
    if _cfg.opik.get("enabled", False):
        try:
            import opik
            api_key = _get_env(_cfg.opik.get("api_key_env", "OPIK_API_KEY"))
            workspace = _get_env(_cfg.opik.get("workspace_env", "OPIK_WORKSPACE"))
            project_name = _cfg.opik.get("project_name", "smart-lock-agent")
            tags = _cfg.opik.get("tags", [])
            opik.configure(
                api_key=api_key,
                workspace=workspace or None,
                project_name=project_name,
                force=True,
            )
            # 抑制 OPIK 非關鍵日誌（必須在 configure 之後，否則會被 OPIK setup 覆蓋）
            logging.getLogger("opik").setLevel(logging.CRITICAL)

            from opik.integrations.langchain import OpikTracer
            opik_tracer = OpikTracer(
                project_name=project_name,
                tags=tags,
            )
            print(f"[*] OPIK tracing enabled (project={project_name})")
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
    await data_correction.close_db()
    print("[*] Connections closed")


# ── /health helpers ──

import time
from fastapi.responses import JSONResponse


async def _timed_check(coro, timeout: float = 3.0) -> dict:
    """Run a check coroutine with timeout, return {status, latency_ms} on success
    or {status, error} on failure. Never raises — every error is captured.
    """
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        latency = (time.perf_counter() - start) * 1000
        return {"status": "timeout", "latency_ms": round(latency, 1),
                "error": f"exceeded {timeout}s"}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        # Trim long stack messages and avoid leaking internals
        msg = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
        return {"status": "error", "latency_ms": round(latency, 1), "error": msg}

    latency = (time.perf_counter() - start) * 1000
    payload = {"status": "ok", "latency_ms": round(latency, 1)}
    if isinstance(result, dict):
        # Allow checks to return extra metadata (e.g. skill count)
        payload.update(result)
    return payload


async def _check_facts_db() -> dict:
    """Ping facts DB via SELECT 1 — sync auto-reconnect through _ensure_conn()."""
    import profiles.manager as pm
    if not await pm._ensure_conn():
        raise RuntimeError("facts DB connection unavailable")
    await pm._facts_conn.execute("SELECT 1")
    return {}


async def _check_audit_db() -> dict:
    """Ping audit DB via SELECT 1."""
    import storage.postgres_impl as audit
    if not await audit._ensure_conn():
        raise RuntimeError("audit DB connection unavailable")
    await audit._postgres_conn.execute("SELECT 1")
    return {}


async def _check_memory_db() -> dict:
    """Ping memory backend (only meaningful for postgres / sqlite)."""
    if _cfg is None:
        raise RuntimeError("config not loaded")
    mem_type = _cfg.memory.get("type", "memory")

    if mem_type == "postgres":
        from memory import postgres_saver as ps
        conn = ps._postgres_conn
        if conn is None or conn.closed or conn.broken:
            raise RuntimeError("memory postgres connection broken")
        await conn.execute("SELECT 1")
        return {"backend": "postgres"}

    if mem_type == "sqlite":
        from memory import sqlite_saver as ss
        if ss._sqlite_conn is None:
            raise RuntimeError("memory sqlite connection not initialised")
        async with ss._sqlite_conn.execute("SELECT 1") as cur:
            await cur.fetchone()
        return {"backend": "sqlite"}

    # In-process MemorySaver — nothing to ping, always ok
    return {"backend": mem_type}


async def _check_llm() -> dict:
    """Verify LLM client is constructed and config is valid.

    NOTE: We deliberately do NOT issue a real LLM request here — that would
    cost tokens, add latency, and risk false alarms from quota throttling.
    Instead we check the static configuration that startup() validated.
    """
    if _cfg is None:
        raise RuntimeError("config not loaded")
    model = _cfg.llm.get("model")
    if not model:
        raise RuntimeError("llm.model not configured")
    return {"model": model}


async def _check_media_storage() -> dict:
    """Verify media storage backend was initialised by startup()."""
    import harness.multimodal as mm
    if mm._media_storage is None:
        # multimodal disabled is a valid state — surface as ok with detail
        if not mm.is_enabled():
            return {"backend": "disabled"}
        raise RuntimeError("media storage not initialised but multimodal enabled")
    backend_cls = type(mm._media_storage).__name__
    return {"backend": backend_cls}


async def _check_skill_registry() -> dict:
    """Re-scan skills directory and report count.

    This catches deployment misconfigs (missing data/, broken frontmatter, etc.).
    """
    if _cfg is None:
        raise RuntimeError("config not loaded")
    from skills import load_skills
    skills_dir = _cfg.skills.get("data_dir", "skills/data")
    skills = load_skills(skills_dir)
    if not skills:
        raise RuntimeError(f"no skills loaded from {skills_dir}")
    return {"count": len(skills)}


@app.get("/health")
async def health():
    """Health check — pings DB / LLM config / media storage / skill registry.

    Returns 200 + {status: "ok"} when every check passes, 503 + {status: "degraded"}
    if any check fails. Individual check failures are isolated (one failure does
    not crash the endpoint).
    """
    facts_db, audit_db, memory_db, llm, media_storage, skill_registry = await asyncio.gather(
        _timed_check(_check_facts_db(), timeout=3.0),
        _timed_check(_check_audit_db(), timeout=3.0),
        _timed_check(_check_memory_db(), timeout=3.0),
        _timed_check(_check_llm(), timeout=2.0),
        _timed_check(_check_media_storage(), timeout=2.0),
        _timed_check(_check_skill_registry(), timeout=5.0),
    )

    checks = {
        "facts_db": facts_db,
        "audit_db": audit_db,
        "memory_db": memory_db,
        "llm": llm,
        "media_storage": media_storage,
        "skill_registry": skill_registry,
    }

    all_ok = all(c["status"] == "ok" for c in checks.values())
    body = {
        "status": "ok" if all_ok else "degraded",
        "version": "2.0-skills",
        "checks": checks,
    }
    return JSONResponse(status_code=200 if all_ok else 503, content=body)


@app.get("/chat")
async def chat_test(q: str = "你好", user_id: str = "test-cli"):
    """GET /chat?q=門打不開&user_id=xxx — 快速測試用（不經 debounce）。

    `user_id` 可覆蓋（eval/批次測試需要每題獨立 thread 以避免 checkpointer 串線）。
    """
    # OTel: tag the current HTTP span with user_id for trace filtering
    from opentelemetry import trace as _otel_trace

    span = _otel_trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute("app.user_id", user_id)

    answer = await debounce.run_agent(user_id, q)
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

    # OTel: tag the webhook span with line_user_id of the first event for trace filtering
    from opentelemetry import trace as _otel_trace

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = event.source.user_id
        reply_token = event.reply_token

        _span = _otel_trace.get_current_span()
        if _span and _span.is_recording():
            _span.set_attribute("app.line_user_id", user_id)

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
