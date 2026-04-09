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

_postgres_conn = None

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


class PostgresAuditStorage:
    def __init__(self, conn: AsyncConnection):
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

        # Mask PII in payload
        masked_payload = None
        if payload:
            masked_payload = _mask_pii(json.dumps(payload, ensure_ascii=False, default=str))

        await self._conn.execute(
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
        await self._conn.commit()

    # --- Convenience methods for common events ---

    async def log_tool_invocation(
        self, user_id: str, agent_name: str, tool_name: str,
        risk_level: str = "read", args_summary: str = "", result_summary: str = "",
    ):
        await self.log_event(
            event_type="tool_invocation",
            actor_id=user_id,
            actor_role="agent",
            action=f"tool.invoke.{tool_name}",
            target_type="tool",
            target_id=tool_name,
            payload={
                "agent_name": agent_name,
                "risk_level": risk_level,
                "args_summary": args_summary[:200],
                "result_summary": result_summary[:200],
            },
        )

    async def log_safety_gate(
        self, user_id: str, decision: str, risks: list[dict],
        sentiment_level: str = "", red_code: bool = False,
    ):
        await self.log_event(
            event_type="safety_gate",
            actor_id=user_id,
            actor_role="system",
            action=f"safety.{'block' if decision == 'blocked' else 'pass'}",
            target_type="user",
            target_id=user_id,
            payload={
                "decision": decision,
                "risks_count": len(risks),
                "sentiment_level": sentiment_level,
                "red_code": red_code,
            },
        )

    async def log_escalation(
        self, user_id: str, reason: str, problem_card_id: str = "",
        from_agent: str = "", diagnosis_summary: str = "",
    ):
        await self.log_event(
            event_type="escalation",
            actor_id=user_id,
            actor_role="system",
            action="escalation.transfer_human",
            target_type="problem_card",
            target_id=problem_card_id,
            payload={
                "reason": reason,
                "from_agent": from_agent,
                "diagnosis_summary": diagnosis_summary[:300],
            },
        )

    async def log_llm_interaction(
        self, user_id: str, model: str, node_name: str,
        input_tokens: int = 0, output_tokens: int = 0,
        latency_ms: float = 0.0, cost_usd: float = 0.0,
    ):
        await self.log_event(
            event_type="llm_interaction",
            actor_id=user_id,
            actor_role="system",
            action=f"llm.invoke.{node_name}",
            target_type="model",
            target_id=model,
            payload={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "latency_ms": round(latency_ms, 1),
                "estimated_cost_usd": round(cost_usd, 6),
            },
        )

    async def log_rag_citation(
        self, user_id: str, agent_name: str, tool_name: str,
        query: str = "", result_count: int = 0,
    ):
        await self.log_event(
            event_type="rag_citation",
            actor_id=user_id,
            actor_role="agent",
            action=f"rag.retrieve.{tool_name}",
            target_type="knowledge_source",
            target_id=tool_name,
            payload={
                "query": query[:200],
                "agent_name": agent_name,
                "result_count": result_count,
            },
        )


async def build_postgres_storage(config: dict) -> PostgresAuditStorage:
    global _postgres_conn
    uri = os.getenv(config.get("postgres_uri_env", "POSTGRES_URI"))
    print(f"[*] 初始化審計日誌模組: 連線至 PostgreSQL")
    conn = await AsyncConnection.connect(uri)
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
    await conn.commit()
    _postgres_conn = conn
    return PostgresAuditStorage(conn)


async def close_postgres_storage():
    global _postgres_conn
    if _postgres_conn is not None:
        await _postgres_conn.close()
        _postgres_conn = None
