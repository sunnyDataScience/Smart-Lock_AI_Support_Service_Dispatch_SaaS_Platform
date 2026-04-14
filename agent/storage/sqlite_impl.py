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

    async def log_llm_interaction(self, *args, **kwargs):
        pass

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
    await conn.commit()
    _sqlite_conn = conn
    return SqliteAuditStorage(conn)


async def close_sqlite_storage():
    global _sqlite_conn
    if _sqlite_conn is not None:
        await _sqlite_conn.close()
        _sqlite_conn = None
