"""Audit Log 業務邏輯。

讀 `audit_events` 表（Schema_v2_extensions.sql 的結構化稽核事件表），
mapping 成 OpenAPI `AuditLogEntry` schema：
  - event_type → log_type（enum 不在白名單時 fallback 'admin_action'）
  - actor_id / action / payload(→details) / created_at 直接對應

audit_events 沒有 tenant_id，本期不做 tenant 過濾（audit 為部署層級事件）。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

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


# ─────────────────────────────────────────────────────────────────────────────
# Export helpers — F-020 / E7x §4.2 P1
# ─────────────────────────────────────────────────────────────────────────────

# Hard cap for synchronous CSV export.  Beyond this we should hand off to a
# background job + email, but the async path is not implemented yet (returns 202
# stub at the router layer).
SYNC_EXPORT_THRESHOLD = 100_000

# CSV header order — mirrors audit_events table columns.  payload is dumped
# as JSON string so spreadsheets keep it in a single cell.
EXPORT_CSV_COLUMNS = [
    "event_id",
    "timestamp",
    "event_type",
    "actor_id",
    "actor_role",
    "action",
    "target_type",
    "target_id",
    "ip_address",
    "payload",
]


def _build_export_filters(
    *,
    from_: str | datetime | None,
    to: str | datetime | None,
    event_types: list[str] | None,
    actor_id: str | None,
    resource_type: str | None,
) -> tuple[str, list[Any]]:
    """Compose a WHERE clause + arg list for export queries.

    Pulled out of the streaming function so count + stream stay in lockstep —
    both must apply identical predicates.
    """
    where: list[str] = []
    args: list[Any] = []

    if event_types:
        placeholders = ", ".join(["%s"] * len(event_types))
        where.append(f"event_type IN ({placeholders})")
        args.extend(event_types)
    if from_:
        where.append("created_at >= %s")
        args.append(from_)
    if to:
        where.append("created_at <= %s")
        args.append(to)
    if actor_id:
        where.append("actor_id = %s::uuid")
        args.append(actor_id)
    if resource_type:
        where.append("target_type = %s")
        args.append(resource_type)

    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    return where_sql, args


async def count_audit_events(
    *,
    from_: str | datetime | None = None,
    to: str | datetime | None = None,
    event_types: list[str] | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
) -> int:
    """Estimate matching row count to decide sync vs async path."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where_sql, args = _build_export_filters(
        from_=from_,
        to=to,
        event_types=event_types,
        actor_id=actor_id,
        resource_type=resource_type,
    )
    sql = f"SELECT COUNT(*) FROM audit_events {where_sql}"
    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()
    return int(row[0]) if row else 0


async def stream_audit_events(
    *,
    from_: str | datetime | None = None,
    to: str | datetime | None = None,
    event_types: list[str] | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    batch_size: int = 1000,
) -> AsyncIterator[dict[str, Any]]:
    """Yield matching audit_events rows as dicts, ordered by created_at DESC.

    Uses keyset pagination on (created_at, id) to keep memory bounded — the
    common 'OFFSET' pattern degrades quadratically and we may stream up to
    100k rows per request.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where_sql_base, base_args = _build_export_filters(
        from_=from_,
        to=to,
        event_types=event_types,
        actor_id=actor_id,
        resource_type=resource_type,
    )

    last_ts: datetime | None = None
    last_id: str | None = None

    while True:
        where_sql = where_sql_base
        args = list(base_args)
        if last_ts is not None and last_id is not None:
            connector = "AND" if where_sql else "WHERE"
            where_sql = f"{where_sql}{connector} (created_at, id) < (%s, %s::uuid) "
            args.extend([last_ts, last_id])

        sql = (
            "SELECT id, event_type, actor_id, actor_role, action, "
            "target_type, target_id, payload, ip_address, created_at "
            "FROM audit_events "
            f"{where_sql}"
            "ORDER BY created_at DESC, id DESC "
            "LIMIT %s"
        )
        args.append(batch_size)
        cur = await db_module._conn.execute(sql, args)
        rows = await cur.fetchall()
        if not rows:
            return
        for r in rows:
            yield {
                "event_id": str(r[0]),
                "timestamp": r[9].isoformat() if r[9] else "",
                "event_type": r[1] or "",
                "actor_id": str(r[2]) if r[2] else "",
                "actor_role": r[3] or "",
                "action": r[4] or "",
                "target_type": r[5] or "",
                "target_id": str(r[6]) if r[6] else "",
                "ip_address": r[8] or "",
                "payload": json.dumps(r[7], ensure_ascii=False, sort_keys=True)
                if r[7]
                else "",
            }
        if len(rows) < batch_size:
            return
        last_row = rows[-1]
        last_ts = last_row[9]
        last_id = str(last_row[0])


async def log_event(
    *,
    event_type: str,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert a single audit event.  Used to record export requests themselves.

    Failures are logged but not raised — audit logging must never break the
    primary user flow.
    """
    if not await _ensure_conn():
        logger.warning("audit log_event skipped: DB unavailable")
        return
    sql = (
        "INSERT INTO audit_events "
        "(event_type, actor_id, actor_role, action, target_type, target_id, payload, ip_address) "
        "VALUES (%s, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb, %s)"
    )
    try:
        await db_module._conn.execute(
            sql,
            [
                event_type,
                actor_id,
                actor_role,
                action,
                target_type,
                target_id,
                json.dumps(payload, ensure_ascii=False) if payload else None,
                ip_address,
            ],
        )
    except Exception as exc:  # noqa: BLE001 — pragma: no cover; best-effort logging, must not fail caller
        logger.warning("audit log_event failed: %s", exc)


async def log_event_returning_id(
    *,
    event_type: str,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> str:
    """Insert an audit event and RETURN its id.

    Unlike :func:`log_event`, callers here NEED the id (e.g. cancellation.audit_event_id
    is NOT NULL), so a failure must propagate rather than be swallowed.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    sql = (
        "INSERT INTO audit_events "
        "(event_type, actor_id, actor_role, action, target_type, target_id, payload, ip_address) "
        "VALUES (%s, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb, %s) "
        "RETURNING id"
    )
    cur = await db_module._conn.execute(
        sql,
        [
            event_type,
            actor_id,
            actor_role,
            action,
            target_type,
            target_id,
            json.dumps(payload, ensure_ascii=False) if payload else None,
            ip_address,
        ],
    )
    row = await cur.fetchone()
    return str(row[0])
