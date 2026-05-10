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
    PostbackEvent,
    TextMessageContent,
    ImageMessageContent,
    AudioMessageContent,
    VideoMessageContent,
    StickerMessageContent,
)

from core.config import load_config
from core.logging_config import get_logger
from llms import get_llm
from memory import get_checkpointer, close_checkpointer
from profiles import ProfileManager, init_facts_db, close_facts_db
from storage import get_storage, close_storage
from agent import build_agent, get_system_prompt

import core.line_bot as line_bot
import harness.debounce as debounce
import harness.multimodal as multimodal
import harness.memory_manager as memory_manager
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate
import harness.output_validator as output_validator
import harness.data_correction as data_correction

log = get_logger(__name__)

# OpenTelemetry tracing — soft import so missing opentelemetry-sdk on the
# host (e.g. before `uv sync` after pyproject restore) does not break startup.
try:
    from core.tracing import configure_tracing, instrument_fastapi
    configure_tracing(service_name="smart-lock-agent")
    _OTEL_READY = True
except ImportError as _otel_err:
    log.warning("otel_disabled", error=str(_otel_err))
    _OTEL_READY = False

app = FastAPI(title="Smart Lock AI Agent — Product Info")
if _OTEL_READY:
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
    log.info("config_loaded", domain=_cfg.system.get("domain", "")[:30])

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
        "max_reply_length": line_cfg.get("max_reply_length", 5000),
    })

    # 註冊通知 channel adapters（V1.0 只 LINE 真實，SMS/Email/FCM 為 V1.5+ stub）
    # 必須在 line_bot.init 之後，因為 LineChannelAdapter 包裝其全域狀態。
    from notifications import register_default_channels
    register_default_channels()

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

    # 注入 LLM 用量紀錄共用 storage（取代 Opik 的 token + latency 紀錄角色）
    from harness import llm_metrics
    llm_metrics.set_storage(audit_storage)

    # 初始化安全閘門 (H6)
    safety_gate.init(_cfg.safety)

    # 初始化 Quick Reply 快速回覆（須在 output_validator 之前，因驗證器會取品牌/型號清單）
    from harness.line_ui_factory import init_quick_reply
    init_quick_reply(_cfg.quick_reply)

    # 初始化輸出驗證器 (H7.5)
    output_validator.init(model, _cfg.output_validator)

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
            log.info("opik_enabled", project=project_name)
        except Exception as e:
            log.warning("opik_init_failed", error=str(e), exc_info=True)

    # 初始化 debounce (H3)
    debounce_config = {
        **_cfg.debounce,
        "request_timeout": _cfg.system.get("request_timeout", 60),
        "max_reply_length": line_cfg.get("max_reply_length", 5000),
    }
    debounce.init(
        agent, debounce_config, _cfg.templates,
        profile_mgr=profile_mgr,
        audit_storage=audit_storage,
        opik_tracer=opik_tracer,
        system_prompt_getter=get_system_prompt,
        conversation_id_getter=get_cached_conversation_id,
    )

    # 初始化 multimodal (H2)
    await multimodal.init(_cfg.multimodal, access_token)

    # 啟動背景清理任務
    asyncio.create_task(debounce.cleanup_stale_buffers())

    log.info("agent_ready", layers=["skill", "debounce", "multimodal", "audit"])


@app.on_event("shutdown")
async def shutdown():
    await multimodal.close()
    await close_storage()
    await close_checkpointer()
    await close_facts_db()
    await data_correction.close_db()
    log.info("connections_closed")


@app.get("/health")
async def health():
    """Health check — 驗證核心 DB pool 是否存活。

    對每個 pool 執行 SELECT 1，驗證的不是「曾經連上過」而是「現在拿得到一條活的連線」，
    這是上一輪事件（checkpointer 死掉但 health 仍回 200）的修復點。
    """
    from fastapi.responses import JSONResponse
    import profiles.manager as pm
    import storage.postgres_impl as audit
    import memory.postgres_saver as ckpt
    import harness.data_correction as dc

    pools = {
        "checkpointer": ckpt.get_pool(),
        "facts_db": pm.get_pool(),
        "audit_db": audit.get_pool(),
        "data_correction_db": dc.get_pool(),
    }

    checks: dict[str, str] = {}
    for name, pool in pools.items():
        if pool is None:
            checks[name] = "disabled"
            continue
        if pool.closed:
            checks[name] = "closed"
            continue
        try:
            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
            checks[name] = "ok"
        except Exception as e:
            checks[name] = f"error: {type(e).__name__}"

    # disabled 視為 ok（功能本來就關閉）；只有 closed / error 算 degraded
    degraded = any(v not in ("ok", "disabled") for v in checks.values())
    return JSONResponse(
        status_code=503 if degraded else 200,
        content={"status": "degraded" if degraded else "ok", "version": "2.0-skills", "checks": checks},
    )


@app.get("/chat")
async def chat_test(q: str = "你好", user_id: str = "test-cli"):
    """GET /chat?q=門打不開&user_id=xxx — 快速測試用（不經 debounce）。

    `user_id` 可覆蓋（eval/批次測試需要每題獨立 thread 以避免 checkpointer 串線）。
    """
    answer = await debounce.run_agent(user_id, q)
    return {"answer": answer}


# ── F2 客戶改期 RSVP postback handler ──


async def _handle_reschedule_postback(event):
    """處理 LINE Flex 改期 postback（Flow 11 客戶端 RSVP）。

    解析 postback data → 呼叫內部 api endpoint 確認/拒絕 → 回覆客戶確認訊息。
    """
    import os
    import uuid as _uuid

    import httpx

    from harness.reschedule_flex import parse_postback_data

    logger = logging.getLogger("agent.reschedule_postback")
    raw_data = getattr(event.postback, "data", "") if event.postback else ""
    parsed = parse_postback_data(raw_data)
    if not parsed:
        return  # 非本模組事件

    api_base = os.environ.get(
        "INTERNAL_API_BASE_URL", "http://localhost:8001"
    )
    tenant_id = os.environ.get(
        "INTERNAL_API_TENANT_ID", "00000000-0000-0000-0000-000000000001"
    )
    api_token = os.environ.get("INTERNAL_API_BEARER", "")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "X-Tenant-ID": tenant_id,
        "Idempotency-Key": str(_uuid.uuid4()),
        "Content-Type": "application/json",
    }

    wo_id = parsed.get("wo")
    if not wo_id:
        return

    reply_text: str
    async with httpx.AsyncClient(timeout=10) as client:
        if parsed["action"] == "reschedule_select":
            res = await client.post(
                f"{api_base}/api/v1/work-orders/{wo_id}/reschedule/customer-confirm",
                json={
                    "selected_start": parsed.get("start", ""),
                    "selected_end": parsed.get("end", ""),
                },
                headers=headers,
            )
            if res.status_code == 200:
                reply_text = (
                    f"已收到您選擇的時段，我們會通知技師。如需調整請來訊告知。"
                )
            else:
                logger.warning(
                    "customer-confirm failed: %s %s",
                    res.status_code,
                    res.text[:200],
                )
                reply_text = "確認時段失敗，請稍後再試或來訊與我們聯繫。"
        elif parsed["action"] == "reschedule_reject":
            await client.post(
                f"{api_base}/api/v1/work-orders/{wo_id}/reschedule/customer-reject",
                headers=headers,
            )
            reply_text = "已通知技師您不便這幾個時段，我們會儘速重新安排。"
        else:
            return

    # 回覆客戶
    try:
        from core import line_bot
        from linebot.v3.messaging import TextMessage

        await line_bot.send_response(
            event.source.user_id,
            event.reply_token,
            [TextMessage(text=reply_text)],
        )
    except Exception:
        logger.exception("failed to send reschedule reply")


# ── F-001 ServiceTicket bridge: ensure conversation record exists ──
#
# ADR-009 D pattern (HTTP call) — 在 LINE webhook 第一筆訊息建立 conversation
# record，讓 admin dashboard 能看到客戶活動。Cache 30 min（對齊 LINE session
# idle timeout），每筆訊息走 cache fast-path 不重打 admin API。

_CONVERSATION_CACHE: dict[str, tuple[str, float]] = {}  # line_user_id -> (conv_id, expire_ts)
_CONVERSATION_TTL_SEC = 30 * 60  # 30 min


async def _ensure_conversation_record(
    line_user_id: str, *, display_name: str | None = None
) -> str | None:
    """確保 conversation record 已存在，回 conversation_id。

    Cache TTL 30 min；首次或過期觸發 AdminAPIClient.create_conversation。
    Fail-soft：失敗回 None，不阻塞 LINE webhook。
    """
    import time

    now = time.time()
    cached = _CONVERSATION_CACHE.get(line_user_id)
    if cached and cached[1] > now:
        return cached[0]

    try:
        from integrations import AdminAPIClient

        client = AdminAPIClient.from_env()
        # session_id 用 line_user_id + 時段 hash（30 min window）
        session_window = int(now // _CONVERSATION_TTL_SEC)
        session_id = f"line-{line_user_id}-{session_window}"

        conv = await client.create_conversation(
            line_user_id=line_user_id,
            session_id=session_id,
            display_name=display_name,
            channel="line",
            idempotency_key=f"{line_user_id}:{session_id}:F-001-conv",
        )
        if conv:
            conv_id = conv.get("id")
            if conv_id:
                _CONVERSATION_CACHE[line_user_id] = (conv_id, now + _CONVERSATION_TTL_SEC)
                return conv_id
    except Exception:  # noqa: BLE001 — fail-soft on bridge failure
        logger.exception("F-001 ensure_conversation_record failed (non-fatal)")

    return None


def get_cached_conversation_id(line_user_id: str) -> str | None:
    """Public read-only accessor for ``_CONVERSATION_CACHE`` (used by harness).

    Cache 由 ``_ensure_conversation_record`` 在每筆 webhook 進來時 prime；本函式
    僅查表，不會主動建 conversation。Returns None on cache miss / expired.
    """
    import time

    cached = _CONVERSATION_CACHE.get(line_user_id)
    if cached and cached[1] > time.time():
        return cached[0]
    return None


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
        # ── PostbackEvent：F2 LINE Flex RSVP（Flow 11 客戶改期確認）──
        if isinstance(event, PostbackEvent):
            try:
                await _handle_reschedule_postback(event)
            except Exception:
                logger.exception("postback handler failed")
            continue

        if not isinstance(event, MessageEvent):
            continue

        user_id = event.source.user_id
        reply_token = event.reply_token

        # ── F-001 bridge: 確保 conversation record 已建立（fire-and-forget 不阻塞）──
        asyncio.create_task(_ensure_conversation_record(user_id))

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
                log.info("media_received", media_type=media_type, user_id=user_id, msg_id=message_id)
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

            log.info("text_received", user_id=user_id, text_preview=text[:50])
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
        log.error("media_handler_error", media_type=media_type, user_id=user_id, error=str(e), exc_info=True)
        debounce.add_message_to_buffer(
            user_id, None,
            f"[使用者傳送了{media_label}，但系統無法下載內容，請根據對話脈絡盡量協助]",
            replace_media_pending=True,
        )
