"""PostgreSQL audit storage with structured event types.

Event types:
  - conversation:      AI agent chat messages (90-day retention)
  - tool_invocation:   Tool call + result summary (90-day retention)
  - safety_gate:       Safety layer gate decisions (1-year retention)
  - escalation:        Human handoff events (1-year retention)
  - dispatch_decision: Dispatch matching (2-year retention, V2.0)
  - financial_action:  Refunds/payments (7-year retention, V2.0)
  - admin_action:      Role/config changes (7-year retention, V2.0)
"""

import json
import os
import re
from datetime import datetime, timezone
from psycopg import AsyncConnection

_postgres_conn: AsyncConnection | None = None
_postgres_uri_env: str = ""

# PII masking patterns
_PII_PATTERNS = [
    (re.compile(r'09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}'), lambda m: m.group()[:4] + "-XXX-XXX"),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), lambda m: m.group()[0] + "***@" + m.group().split("@")[1]),
    (re.compile(r'[A-Z][12]\d{8}'), lambda m: m.group()[0] + "XXXXXXXXX"),
]


def _mask_pii(text: str) -> str:
    """Mask PII in text: phone → 09XX-XXX-XXX, email → a***@domain, ID → AXXXXXXXXX."""
    for pattern, replacer in _PII_PATTERNS:
        text = pattern.sub(replacer, text)
    return text


async def _ensure_conn() -> bool:
    """檢查連線健康度，必要時自動重連。"""
    global _postgres_conn
    if _postgres_conn is not None and not _postgres_conn.closed and not _postgres_conn.broken:
        return True
    uri = os.getenv(_postgres_uri_env)
    if not uri:
        return False
    try:
        if _postgres_conn is not None:
            try:
                await _postgres_conn.close()
            except Exception:
                pass
        _postgres_conn = await AsyncConnection.connect(uri, autocommit=True)
        print("[Audit DB] 重新連線成功")
        return True
    except Exception as e:
        print(f"[Audit DB] 重新連線失敗: {e}")
        _postgres_conn = None
        return False


class PostgresAuditStorage:

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
        if not await _ensure_conn():
            return
        timestamp = datetime.now(timezone.utc).isoformat()

        # Mask PII in payload
        masked_payload = None
        if payload:
            masked_payload = _mask_pii(json.dumps(payload, ensure_ascii=False, default=str))

        try:
            await _postgres_conn.execute(
                """INSERT INTO audit_log
                   (user_id, role, content, timestamp, event_type, action, target_type, target_id, payload)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    actor_id,
                    actor_role,
                    payload.get("content", "") if payload else "",
                    timestamp,
                    event_type,
                    action,
                    target_type,
                    target_id,
                    masked_payload,
                ),
            )
        except Exception as e:
            print(f"[Audit DB] log_event 失敗: {e}")

    # --- Convenience methods for common events ---

    async def log_tool_invocation(self, *args, **kwargs):
        pass

    async def log_safety_gate(self, *args, **kwargs):
        pass

    async def log_escalation(self, *args, **kwargs):
        pass

    async def log_llm_interaction(self, *args, **kwargs):
        pass

async def build_postgres_storage(config: dict) -> PostgresAuditStorage:
    global _postgres_conn, _postgres_uri_env
    _postgres_uri_env = config.get("postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(_postgres_uri_env)
    print(f"[*] 初始化審計日誌模組: 連線至 PostgreSQL")
    conn = await AsyncConnection.connect(uri, autocommit=True)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL
        )
    """)
    for col_def in [
        "event_type VARCHAR(50) DEFAULT 'conversation'",
        "action VARCHAR(100) DEFAULT ''",
        "target_type VARCHAR(50) DEFAULT ''",
        "target_id VARCHAR(100) DEFAULT ''",
        "payload JSONB",
    ]:
        try:
            await conn.execute(f"ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS {col_def}")
        except Exception:
            pass
    _postgres_conn = conn
    return PostgresAuditStorage()


async def close_postgres_storage():
    global _postgres_conn
    if _postgres_conn is not None:
        await _postgres_conn.close()
        _postgres_conn = None
