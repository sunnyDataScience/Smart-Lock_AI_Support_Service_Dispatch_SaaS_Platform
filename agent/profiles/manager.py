import os
import psycopg
from psycopg_pool import AsyncConnectionPool


# Pool 取代單一 conn — checkout 時自動驗證並回收壞掉的連線（同 checkpointer 修法）。
_facts_pool: AsyncConnectionPool | None = None
_facts_uri_env: str = ""


def get_pool() -> AsyncConnectionPool | None:
    """供 /health 等模組讀取 pool 健康狀態。"""
    return _facts_pool


async def _verify_required_tables(conn) -> None:
    """Schema 單一真相來源原則：runtime 不再建表，啟動時只驗證表存在。

    若表不存在，明確要求 operator 跑 schema migration（SQL/Schema_harness_migration.sql）。
    """
    for table in ("user_facts", "user_soft_profiles"):
        try:
            await conn.execute(f"SELECT 1 FROM {table} LIMIT 0")
        except psycopg.errors.UndefinedTable:
            raise RuntimeError(
                f"Required table '{table}' missing. Run schema migration: "
                f"psql $POSTGRES_URI < SQL/Schema_harness_migration.sql"
            ) from None


async def init_facts_db(config: dict):
    """Initialize the facts DB pool from config."""
    global _facts_pool, _facts_uri_env
    _facts_uri_env = config.get("facts_postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(_facts_uri_env)
    if not uri:
        print(f"[Facts DB] 警告：環境變數 {_facts_uri_env} 未設定，facts 功能降級為停用")
        return
    try:
        pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=1,
            max_size=int(config.get("pool_max_size", 10)),
            max_idle=float(config.get("pool_max_idle_seconds", 240)),
            timeout=float(config.get("pool_checkout_timeout", 30)),
            kwargs={"autocommit": True},
            open=False,
            check=AsyncConnectionPool.check_connection,
        )
        await pool.open(wait=True)

        async with pool.connection() as conn:
            await _verify_required_tables(conn)

        _facts_pool = pool
        print("[Facts DB] 已連線至 PostgreSQL（user_facts + user_soft_profiles, pool）")
    except Exception as e:
        print(f"[Facts DB] 連線失敗，降級為停用: {e}")
        _facts_pool = None


async def close_facts_db():
    """Close the facts DB pool."""
    global _facts_pool
    if _facts_pool is not None:
        await _facts_pool.close()
        _facts_pool = None


class ProfileManager:
    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.facts_enabled = config.get("facts_enabled", False)
        self.fact_attributes = config.get("fact_attributes", [])

    async def load_profile(self, user_id: str) -> str:
        if not self.enabled or _facts_pool is None:
            return ""
        try:
            async with _facts_pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT content FROM user_soft_profiles WHERE user_id = %s",
                    (user_id,),
                )
                row = await cursor.fetchone()
                return row[0] if row else ""
        except Exception as e:
            print(f"[Profile DB] load_profile 失敗: {e}")
            return ""

    async def save_profile(self, user_id: str, content: str) -> None:
        if not self.enabled or _facts_pool is None:
            return
        try:
            async with _facts_pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO user_soft_profiles (user_id, content, updated_at) "
                    "VALUES (%s, %s, NOW()) "
                    "ON CONFLICT (user_id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()",
                    (user_id, content),
                )
        except Exception as e:
            print(f"[Profile DB] save_profile 失敗: {e}")

    async def load_facts(self, user_id: str) -> dict:
        """Load current facts from user_facts table."""
        if not self.facts_enabled or _facts_pool is None:
            return {}
        try:
            async with _facts_pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT attr_key, attr_val FROM user_facts WHERE user_id = %s AND is_current = TRUE",
                    (user_id,),
                )
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception as e:
            print(f"[Facts DB] load_facts 失敗: {e}")
            return {}

    async def update_fact(self, user_id: str, attr_key: str, attr_val: str):
        """SCD Type 2 upsert: expire old + insert new，使用 CTE 確保原子性。

        ADR-0030 / Phase C3-a：INSERT 帶 tenant_id（讀 ContextVar，fallback
        'default'）。expire UPDATE 不加 tenant_id 條件以保 backward compat
        （single-tenant 部署所有現有 row tenant_id='default'，filter 等同無
        效；多租戶上線時改 schema 加 NOT NULL 即自動隔離）。
        """
        if not self.facts_enabled or _facts_pool is None:
            return
        try:
            from skills.tools import get_current_tenant
            tenant_id = get_current_tenant()
        except Exception:  # noqa: BLE001
            tenant_id = "default"
        try:
            async with _facts_pool.connection() as conn:
                await conn.execute(
                    "WITH expired AS ("
                    "  UPDATE user_facts SET is_current = FALSE, end_date = NOW() "
                    "  WHERE user_id = %s AND attr_key = %s AND is_current = TRUE AND attr_val != %s"
                    ") "
                    "INSERT INTO user_facts (user_id, attr_key, attr_val, is_current, start_date, tenant_id) "
                    "SELECT %s, %s, %s, TRUE, NOW(), %s "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM user_facts WHERE user_id = %s AND attr_key = %s AND attr_val = %s AND is_current = TRUE"
                    ")",
                    (user_id, attr_key, attr_val,
                     user_id, attr_key, attr_val, tenant_id,
                     user_id, attr_key, attr_val),
                )
        except Exception as e:
            print(f"[Facts DB] update_fact 失敗 ({attr_key}={attr_val}): {e}")

    async def clear_fact(self, user_id: str, attr_key: str):
        """將指定 fact 標記為過期但不寫入新值（用於品牌切換時清掉舊型號）。"""
        if not self.facts_enabled or _facts_pool is None:
            return
        try:
            async with _facts_pool.connection() as conn:
                await conn.execute(
                    "UPDATE user_facts SET is_current = FALSE, end_date = NOW() "
                    "WHERE user_id = %s AND attr_key = %s AND is_current = TRUE",
                    (user_id, attr_key),
                )
        except Exception as e:
            print(f"[Facts DB] clear_fact 失敗 ({attr_key}): {e}")

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
