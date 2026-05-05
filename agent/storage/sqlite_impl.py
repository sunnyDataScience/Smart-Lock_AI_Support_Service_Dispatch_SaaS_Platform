"""SQLite audit storage with structured event types (local dev fallback)."""

import json
from datetime import datetime, timezone

import aiosqlite

_sqlite_conn = None


class SqliteAuditStorage:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    # --- Legacy API (backward compatible) ---

    async def log_message(self, user_id: str, role: str, content: str):
        """Legacy: log a conversation message."""
        await self.log_event(
            event_type="conversation",
            actor_id=user_id,
            actor_role=role,
            action="conversation.message",
            payload={"content": content},
        )

    # --- Structured Event API ---

    async def log_event(
        self,
        event_type: str,
        actor_id: str,
        actor_role: str = "system",
        action: str = "",
        target_type: str = "",
        target_id: str = "",
        payload: dict | None = None,
    ):
        timestamp = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """INSERT INTO audit_log
               (user_id, role, content, timestamp, event_type, action, target_type, target_id, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                actor_id,
                actor_role,
                payload.get("content", "") if payload else "",
                timestamp,
                event_type,
                action,
                target_type,
                target_id,
                json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            ),
        )
        await self._conn.commit()

    async def log_tool_invocation(self, *args, **kwargs):
        pass

    async def log_safety_gate(self, *args, **kwargs):
        pass

    async def log_escalation(self, *args, **kwargs):
        pass

    async def log_llm_interaction(self, user_id: str, model: str, call_site: str = "react_agent", latency_ms: float | int | None = None, **kwargs):
        await self.log_llm_call(
            user_id=user_id,
            call_site=call_site,
            model=model,
            latency_ms=int(latency_ms) if latency_ms is not None else None,
            **kwargs,
        )

    async def log_llm_call(
        self,
        user_id: str,
        call_site: str,
        model: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        success: bool = True,
        error_type: str | None = None,
        turn_id: str | None = None,
        metadata: dict | None = None,
    ):
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            await self._conn.execute(
                """INSERT INTO llm_usage_log
                   (timestamp, user_id, turn_id, call_site, model, input_tokens, output_tokens,
                    total_tokens, latency_ms, success, error_type, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    timestamp,
                    user_id,
                    turn_id,
                    call_site,
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    latency_ms,
                    1 if success else 0,
                    error_type,
                    json.dumps(metadata, ensure_ascii=False, default=str) if metadata else None,
                ),
            )
            await self._conn.commit()
        except Exception as e:
            print(f"[LLM Usage DB] log_llm_call 失敗: {e}")

async def build_sqlite_storage(config: dict) -> SqliteAuditStorage:
    global _sqlite_conn
    db_path = config.get("sqlite_path", "./data/db/audit_log.db")
    print(f"[*] 初始化審計日誌模組: 連線至 SQLite ({db_path})")
    conn = await aiosqlite.connect(db_path)
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT DEFAULT 'conversation',
            action TEXT DEFAULT '',
            target_type TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            payload TEXT
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS llm_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            turn_id TEXT,
            call_site TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms INTEGER,
            success INTEGER NOT NULL DEFAULT 1,
            error_type TEXT,
            metadata TEXT
        )"""
    )
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp ON llm_usage_log(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id ON llm_usage_log(user_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_call_site ON llm_usage_log(call_site, timestamp DESC)",
    ]:
        try:
            await conn.execute(idx_sql)
        except Exception:
            pass
    await conn.commit()
    _sqlite_conn = conn
    return SqliteAuditStorage(conn)


async def close_sqlite_storage():
    global _sqlite_conn
    if _sqlite_conn is not None:
        await _sqlite_conn.close()
        _sqlite_conn = None
