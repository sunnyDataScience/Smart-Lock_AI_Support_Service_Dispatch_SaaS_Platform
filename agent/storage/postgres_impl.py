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

    async def log_llm_interaction(self, user_id: str, model: str, call_site: str = "react_agent", latency_ms: float | int | None = None, **kwargs):
        """Backward-compatible wrapper — forwards to log_llm_call."""
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
        """記錄單次 LLM 呼叫的 token 使用量與延遲（不阻塞回覆關鍵路徑）。

        - 寫入失敗只印 log，不 raise（呼叫端應已用 asyncio.create_task 火放即忘）
        - metadata 僅存結構化欄位（step_index、tool_name、model_temperature 等），禁存訊息原文
        """
        if not await _ensure_conn():
            return
        try:
            await _postgres_conn.execute(
                """INSERT INTO llm_usage_log
                   (user_id, turn_id, call_site, model, input_tokens, output_tokens,
                    total_tokens, latency_ms, success, error_type, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id,
                    turn_id,
                    call_site,
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    latency_ms,
                    success,
                    error_type,
                    json.dumps(metadata, ensure_ascii=False, default=str) if metadata else None,
                ),
            )
        except Exception as e:
            print(f"[LLM Usage DB] log_llm_call 失敗: {e}")

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

    # llm_usage_log: token 使用量 + 延遲度量（取代 Opik 角色）
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage_log (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_id TEXT NOT NULL,
            turn_id TEXT,
            call_site VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms INTEGER,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            error_type VARCHAR(50),
            metadata JSONB
        )
    """)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp ON llm_usage_log(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id ON llm_usage_log(user_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_call_site ON llm_usage_log(call_site, timestamp DESC)",
    ]:
        try:
            await conn.execute(idx_sql)
        except Exception as e:
            print(f"[Audit DB] 建立 llm_usage_log 索引失敗（已忽略）: {e}")

    _postgres_conn = conn
    return PostgresAuditStorage()


async def close_postgres_storage():
    global _postgres_conn
    if _postgres_conn is not None:
        await _postgres_conn.close()
        _postgres_conn = None
