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
            payload={"agent_name": agent_name, "risk_level": risk_level,
                     "args_summary": args_summary[:200], "result_summary": result_summary[:200]},
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
            payload={"decision": decision, "risks_count": len(risks),
                     "sentiment_level": sentiment_level, "red_code": red_code},
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
            payload={"reason": reason, "from_agent": from_agent,
                     "diagnosis_summary": diagnosis_summary[:300]},
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
            payload={"input_tokens": input_tokens, "output_tokens": output_tokens,
                     "total_tokens": input_tokens + output_tokens,
                     "latency_ms": round(latency_ms, 1),
                     "estimated_cost_usd": round(cost_usd, 6)},
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
            payload={"query": query[:200], "agent_name": agent_name,
                     "result_count": result_count},
        )


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
