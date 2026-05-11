"""資料修正攔截模組 — 使用者輸入 #資料修正 時，記錄對話上下文至資料庫。

攔截後不進入 Agent，直接回覆確認訊息。
對話 checkpoint 不受影響，使用者可繼續正常對話。
"""

PHASE: str = "H_DC"  # per harness/__init__.py PIPELINE inventory (ADR-0024 §3 S2)
import os
import json

from psycopg_pool import AsyncConnectionPool

from core.logging_config import get_logger
import psycopg

log = get_logger(__name__)


# ── Module-level state ──
# Pool 取代單一 conn — checkout 時自動驗證並回收壞掉的連線（同 checkpointer 修法）。

_pool: AsyncConnectionPool | None = None
_enabled: bool = False
_keyword: str = "#資料修正"
_reply: str = "已收到您的回報，我們會盡快處理，謝謝您！"
_uri_env: str = ""


def get_pool() -> AsyncConnectionPool | None:
    """供 /health 等模組讀取 pool 健康狀態。"""
    return _pool


async def init_db(config: dict):
    """初始化資料修正模組 — 建立 DB pool 與 table。"""
    global _pool, _enabled, _keyword, _reply, _uri_env

    _enabled = config.get("enabled", False)
    if not _enabled:
        log.info("data_correction_disabled")
        return

    _keyword = config.get("keyword", "#資料修正")
    _reply = config.get("reply", _reply)

    _uri_env = config.get("postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(_uri_env)
    if not uri:
        log.warning("data_correction_uri_missing", env=_uri_env)
        _enabled = False
        return

    try:
        pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=1,
            max_size=int(config.get("pool_max_size", 5)),
            max_idle=float(config.get("pool_max_idle_seconds", 240)),
            timeout=float(config.get("pool_checkout_timeout", 30)),
            kwargs={"autocommit": True},
            open=False,
            check=AsyncConnectionPool.check_connection,
        )
        await pool.open(wait=True)

        async with pool.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS data_corrections (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    note TEXT DEFAULT '',
                    conversation_context TEXT NOT NULL,
                    user_facts JSONB,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dc_user_id ON data_corrections (user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dc_status ON data_corrections (status)"
            )
        _pool = pool
        log.info("data_correction_enabled", keyword=_keyword, mode="pool")
    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("data_correction_db_failed", error=str(e), exc_info=True)
        _enabled = False
        _pool = None


async def close_db():
    """關閉 DB pool。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_and_save(
    user_id: str,
    text: str,
    agent,
    profile_mgr,
) -> str | None:
    """檢查是否為資料修正指令，是則寫入 DB 並回傳回覆文字。

    Args:
        user_id: LINE 用戶 ID
        text: 使用者輸入文字
        agent: LangGraph agent（用於讀取 checkpoint 對話歷史）
        profile_mgr: ProfileManager（用於讀取 user_facts）

    Returns:
        回覆文字（已攔截）或 None（未攔截）
    """
    if not _enabled or _pool is None:
        return None

    stripped = text.strip()
    if not stripped.startswith(_keyword):
        return None

    # 截取補充說明
    note = stripped[len(_keyword):].strip()

    log.info("data_correction_intercepted", user_id=user_id, note_preview=note[:50])

    # 擷取對話歷史
    conversation_context = await _extract_conversation(agent, user_id)

    # 擷取用戶資料
    facts = await _extract_facts(profile_mgr, user_id)

    # 寫入 DB
    try:
        async with _pool.connection() as conn:
            await conn.execute(
                "INSERT INTO data_corrections (user_id, note, conversation_context, user_facts) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, note, conversation_context, json.dumps(facts, ensure_ascii=False)),
            )
        log.info("data_correction_persisted", user_id=user_id)
    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("data_correction_persist_failed", user_id=user_id, error=str(e), exc_info=True)

    return _reply


def _strip_prefix(content: str) -> str:
    """移除注入的 [可用技能] / [用戶資料] 前綴，只保留 [用戶訊息] 之後的實際內容。"""
    marker = "[用戶訊息]\n"
    idx = content.find(marker)
    if idx != -1:
        return content[idx + len(marker):]
    return content


async def _extract_conversation(agent, user_id: str) -> str:
    """從 checkpoint 擷取對話歷史，格式化為純文字。"""
    if not agent:
        return ""

    try:
        thread_id = f"line_{user_id}"
        config = {"configurable": {"thread_id": thread_id}}
        state = await agent.aget_state(config)

        if not state or not state.values:
            return ""

        messages = state.values.get("messages", [])
        lines = []
        for msg in messages:
            role = getattr(msg, "type", "")
            if role == "human":
                content = msg.content if isinstance(msg.content, str) else "[多模態]"
                lines.append(f"用戶: {_strip_prefix(content)}")
            elif role == "ai" and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                lines.append(f"客服: {content}")
        return "\n".join(lines)

    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("data_correction_history_fetch_failed", user_id=user_id, error=str(e), exc_info=True)
        return ""


async def _extract_facts(profile_mgr, user_id: str) -> dict:
    """從 ProfileManager 擷取用戶資料。"""
    if not profile_mgr or not profile_mgr.facts_enabled:
        return {}

    try:
        _, facts = await profile_mgr.load_full_profile_with_facts(user_id)
        return facts
    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("data_correction_profile_fetch_failed", user_id=user_id, error=str(e), exc_info=True)
        return {}
