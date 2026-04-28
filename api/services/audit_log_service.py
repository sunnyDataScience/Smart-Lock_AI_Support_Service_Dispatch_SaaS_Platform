"""Audit Log 業務邏輯。

讀 `audit_events` 表（Schema_v2_extensions.sql 的結構化稽核事件表），
mapping 成 OpenAPI `AuditLogEntry` schema：
  - event_type → log_type（enum 不在白名單時 fallback 'admin_action'）
  - actor_id / action / payload(→details) / created_at 直接對應

audit_events 沒有 tenant_id，本期不做 tenant 過濾（audit 為部署層級事件）。
"""

from __future__ import annotations

import logging
from datetime import datetime

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.audit_log_service")


_VALID_LOG_TYPES = {
    "api_call",
    "llm_interaction",
    "rag_retrieval",
    "admin_action",
    "agent_message",
}

_EVENT_TYPE_TO_LOG_TYPE = {
    "conversation": "agent_message",
    "tool_invocation": "llm_interaction",
    "safety_gate": "admin_action",
    "escalation": "admin_action",
    "dispatch_decision": "admin_action",
    "financial_action": "admin_action",
    "admin_action": "admin_action",
}


def _log_type_to_event_types(log_type: str) -> list[str]:
    """Reverse map OpenAPI log_type enum to raw event_type values.

    Output enum is narrower than DB event_type vocab, so a single log_type
    may correspond to multiple event_types (e.g. admin_action ← {admin_action,
    safety_gate, escalation, dispatch_decision, financial_action}).
    """
    matches = [et for et, lt in _EVENT_TYPE_TO_LOG_TYPE.items() if lt == log_type]
    if log_type in _VALID_LOG_TYPES and log_type not in matches:
        matches.append(log_type)
    return matches or [log_type]


def _coerce_log_type(event_type: str | None) -> str:
    if not event_type:
        return "admin_action"
    if event_type in _VALID_LOG_TYPES:
        return event_type
    return _EVENT_TYPE_TO_LOG_TYPE.get(event_type, "admin_action")


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "log_type": _coerce_log_type(row[1]),
        "actor_id": str(row[2]) if row[2] else None,
        "action": row[3] or "",
        "details": row[4] or None,
        "created_at": row[5].isoformat() if row[5] else None,
    }


async def list_audit_logs(
    *,
    log_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    actor_id: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where: list[str] = []
    args: list = []

    if log_type:
        event_types = _log_type_to_event_types(log_type)
        placeholders = ", ".join(["%s"] * len(event_types))
        where.append(f"event_type IN ({placeholders})")
        args.extend(event_types)
    if start_time:
        where.append("created_at >= %s")
        args.append(start_time)
    if end_time:
        where.append("created_at <= %s")
        args.append(end_time)
    if actor_id:
        where.append("actor_id = %s::uuid")
        args.append(actor_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    sql = (
        "SELECT id, event_type, actor_id, action, payload, created_at "
        "FROM audit_events "
        f"{where_sql}"
        "ORDER BY created_at DESC, id DESC "
        "LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[5].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
