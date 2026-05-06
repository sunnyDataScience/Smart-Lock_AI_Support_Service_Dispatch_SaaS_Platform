import logging
import os

from psycopg import AsyncConnection

from core.pg_pool import get_async_conn, set_cached

logger = logging.getLogger(__name__)


# ── Module-level facts DB connection (global conn pattern) ──
# Kept as a module attribute for backward compatibility (health checks in
# app.py read `pm._facts_conn` directly). Stays in sync with pg_pool's
# "facts" entry through `_ensure_conn`, `init_facts_db`, `close_facts_db`.
_facts_conn: AsyncConnection | None = None
_facts_uri_env: str = ""

_POOL_NAME = "facts"


async def _ensure_conn() -> bool:
    """檢查連線健康度，必要時自動重連。

    內部委派至 `core.pg_pool.get_async_conn` — 真正的 reconnect
    邏輯集中在 helper 內，本函式僅負責 URI 解析與 module-level
    變數同步（給 health check / 既有 caller 用）。
    """
    global _facts_conn
    uri = os.getenv(_facts_uri_env)
    if not uri:
        _facts_conn = None
        set_cached(_POOL_NAME, None)
        return False
    try:
        _facts_conn = await get_async_conn(_POOL_NAME, uri)
        return True
    except Exception as e:
        print(f"[Facts DB] 重新連線失敗: {e}")
        _facts_conn = None
        set_cached(_POOL_NAME, None)
        return False


async def init_facts_db(config: dict):
    """Initialize the facts DB connection from config."""
    global _facts_conn, _facts_uri_env
    _facts_uri_env = config.get("facts_postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(_facts_uri_env)
    if not uri:
        print(f"[Facts DB] 警告：環境變數 {_facts_uri_env} 未設定，facts 功能降級為停用")
        return
    try:
        _facts_conn = await get_async_conn(_POOL_NAME, uri)
        # NOTE: user_facts schema 自 RP1.C.4 起由 SQL/Schema_harness_migration.sql 統一管理，
        # 不再 runtime 動態建立。新環境部署前必須先跑該 SQL 檔。
        # user_soft_profiles 仍 runtime 建表（後續可比照搬遷）。
        await _facts_conn.execute("""
            CREATE TABLE IF NOT EXISTS user_soft_profiles (
                user_id TEXT PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("[Facts DB] 已連線至 PostgreSQL（user_soft_profiles ensured, autocommit=True）")
    except Exception as e:
        print(f"[Facts DB] 連線失敗，降級為停用: {e}")
        _facts_conn = None
        set_cached(_POOL_NAME, None)


async def close_facts_db():
    """Close the facts DB connection."""
    global _facts_conn
    if _facts_conn is not None:
        await _facts_conn.close()
        _facts_conn = None
        set_cached(_POOL_NAME, None)


class ProfileManager:
    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.facts_enabled = config.get("facts_enabled", False)
        self.fact_attributes = config.get("fact_attributes", [])

    async def load_profile(self, user_id: str) -> str:
        if not self.enabled:
            return ""
        if not await _ensure_conn():
            return ""
        try:
            cursor = await _facts_conn.execute(
                "SELECT content FROM user_soft_profiles WHERE user_id = %s",
                (user_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else ""
        except Exception as e:
            print(f"[Profile DB] load_profile 失敗: {e}")
            return ""

    async def save_profile(self, user_id: str, content: str) -> None:
        if not self.enabled:
            return
        if not await _ensure_conn():
            return
        try:
            await _facts_conn.execute(
                "INSERT INTO user_soft_profiles (user_id, content, updated_at) "
                "VALUES (%s, %s, NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()",
                (user_id, content),
            )
        except Exception as e:
            print(f"[Profile DB] save_profile 失敗: {e}")

    async def load_facts(self, user_id: str) -> dict:
        """Load current facts from user_facts table."""
        if not self.facts_enabled:
            return {}
        if not await _ensure_conn():
            return {}
        try:
            cursor = await _facts_conn.execute(
                "SELECT attr_key, attr_val FROM user_facts WHERE user_id = %s AND is_current = TRUE",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            print(f"[Facts DB] load_facts 失敗: {e}")
            return {}

    async def update_fact(self, user_id: str, attr_key: str, attr_val: str):
        """SCD Type 2 upsert: expire old + insert new，使用 CTE 確保原子性。"""
        if not self.facts_enabled:
            return
        if not await _ensure_conn():
            return
        try:
            await _facts_conn.execute(
                "WITH expired AS ("
                "  UPDATE user_facts SET is_current = FALSE, end_date = NOW() "
                "  WHERE user_id = %s AND attr_key = %s AND is_current = TRUE AND attr_val != %s"
                ") "
                "INSERT INTO user_facts (user_id, attr_key, attr_val, is_current, start_date) "
                "SELECT %s, %s, %s, TRUE, NOW() "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM user_facts WHERE user_id = %s AND attr_key = %s AND attr_val = %s AND is_current = TRUE"
                ")",
                (user_id, attr_key, attr_val, user_id, attr_key, attr_val, user_id, attr_key, attr_val),
            )
        except Exception as e:
            print(f"[Facts DB] update_fact 失敗 ({attr_key}={attr_val}): {e}")

    def format_facts(self, facts: dict) -> str:
        """Format facts dict as [Verified Fact] lines."""
        if not facts:
            return ""
        lines = [f"[Verified Fact] {k}: {v}" for k, v in facts.items()]
        return "\n".join(lines)

    async def load_full_profile(self, user_id: str) -> str:
        """Load facts + .md profile combined. Facts section first (higher priority)."""
        profile_text, _ = await self.load_full_profile_with_facts(user_id)
        return profile_text

    async def load_full_profile_with_facts(self, user_id: str) -> tuple[str, dict]:
        """Load facts + .md profile combined, also return raw facts dict."""
        facts = await self.load_facts(user_id)
        facts_text = self.format_facts(facts)
        md_text = await self.load_profile(user_id)

        parts = [p for p in [facts_text, md_text] if p]
        return "\n\n".join(parts), facts
