"""Audit Log 業務邏輯。

讀 `audit_events` 表（Schema_v2_extensions.sql 的結構化稽核事件表），
mapping 成 OpenAPI `AuditLogEntry` schema：
  - event_type → log_type（enum 不在白名單時 fallback 'admin_action'）
  - actor_id / action / payload(→details) / created_at 直接對應

audit_events 沒有 tenant_id，本期不做 tenant 過濾（audit 為部署層級事件）。
"""

from __future__ import annotations

import hashlib
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

# ── TI-AUDIT-03：append-only sha256 hash chain（合規紅線）────────────────────
# entry_hash = sha256(prev_hash + "|" + 正規化內容)；prev_hash 接前一列 entry_hash。
# 竄改任一列內容 → 其 entry_hash 對不上 → verify_audit_chain 偵測得到。
_AUDIT_GENESIS = "GENESIS"

# CR-0166 R1-5：hash-chain prev_hash 讀寫並發競態——兩筆同時讀同一 prev_hash
# → 鏈分叉，verify 誤報。全域 advisory xact-lock 序列化「讀末 hash → INSERT」臨界區。
# xact-scoped（commit/abort 自動釋放，與連線池相容；嚴禁 session 級）。key 為固定
# 常數（單一全域鏈）。lock_timeout 2s 兜底，逾時走 fail-soft（log_event 本 best-effort）。
_AUDIT_CHAIN_LOCK_KEY = 0x10C_A0D17  # "lock audit" 諧音固定鍵


async def _acquire_chain_lock() -> None:
    """取全域稽核鏈 advisory xact-lock（須在顯式交易內呼叫）。"""
    await db_module._conn.execute("SET LOCAL lock_timeout = '2s'")
    await db_module._conn.execute(
        "SELECT pg_advisory_xact_lock(%s)", (_AUDIT_CHAIN_LOCK_KEY,)
    )


def _canonical_audit_content(
    event_type: str | None, actor_id: str | None, actor_role: str | None,
    action: str | None, target_type: str | None, target_id: str | None,
    payload_json: str | None,
) -> str:
    """內容正規化為穩定字串（hash 輸入）。None → 空字串；payload 已是序列化 JSON 文字。"""
    parts = [
        event_type or "", actor_id or "", actor_role or "", action or "",
        target_type or "", target_id or "", payload_json or "",
    ]
    return "\x1f".join(str(p) for p in parts)  # 0x1f unit separator 避免欄位邊界混淆


def _compute_entry_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{content}".encode("utf-8")).hexdigest()


async def _latest_entry_hash() -> str:
    """取最後一列 entry_hash 作 prev_hash；無鏈段 → GENESIS。"""
    cur = await db_module._conn.execute(
        "SELECT entry_hash FROM audit_events WHERE entry_hash IS NOT NULL "
        "ORDER BY created_at DESC, id DESC LIMIT 1"
    )
    row = await cur.fetchone()
    return row[0] if row and row[0] else _AUDIT_GENESIS


async def _chain_fields(
    event_type, actor_id, actor_role, action, target_type, target_id, payload,
) -> tuple[str, str, str | None]:
    """算 (prev_hash, entry_hash, payload_json)；payload_json 同時用於 INSERT 與 hash 內容。"""
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    payload_canon = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else None
    )
    prev_hash = await _latest_entry_hash()
    content = _canonical_audit_content(
        event_type, actor_id, actor_role, action, target_type, target_id, payload_canon
    )
    return prev_hash, _compute_entry_hash(prev_hash, content), payload_json


async def verify_audit_chain(*, limit: int = 1000) -> dict:
    """驗證 audit hash chain 完整性（只驗有 entry_hash 的鏈段，依時序）。

    回 {checked, valid, broken_at}：broken_at 為第一個對不上的列 id（valid=True 時 None）。
    偵測兩類竄改：(1) 列內容被改 → entry_hash 重算不符；(2) 列被刪/插 → prev_hash 鏈接斷。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, event_type, actor_id, actor_role, action, target_type, target_id, "
        "       payload, prev_hash, entry_hash "
        "FROM audit_events WHERE entry_hash IS NOT NULL "
        "ORDER BY created_at ASC, id ASC LIMIT %s",
        (limit,),
    )
    rows = await cur.fetchall()
    expected_prev = _AUDIT_GENESIS
    checked = 0
    for r in rows:
        checked += 1
        payload_json = json.dumps(r[7], ensure_ascii=False, sort_keys=True) if r[7] is not None else None
        content = _canonical_audit_content(
            r[1], str(r[2]) if r[2] else None, r[3], r[4], r[5],
            str(r[6]) if r[6] else None, payload_json,
        )
        recomputed = _compute_entry_hash(r[8] or _AUDIT_GENESIS, content)
        # (1) 內容竄改：entry_hash 對不上；(2) 鏈接斷：prev_hash 不接前一列
        if recomputed != r[9] or (r[8] or _AUDIT_GENESIS) != expected_prev:
            return {"checked": checked, "valid": False, "broken_at": str(r[0])}
        expected_prev = r[9]
    return {"checked": checked, "valid": True, "broken_at": None}


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
        "(event_type, actor_id, actor_role, action, target_type, target_id, payload, "
        " ip_address, prev_hash, entry_hash) "
        "VALUES (%s, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb, %s, %s, %s)"
    )
    try:
        # CR-0166 R1-5：advisory lock 序列化讀末 hash → INSERT（防鏈分叉並發競態）
        async with db_module._conn.transaction():
            await _acquire_chain_lock()
            prev_hash, entry_hash, payload_json = await _chain_fields(
                event_type, actor_id, actor_role, action, target_type, target_id, payload
            )
            await db_module._conn.execute(
                sql,
                [
                    event_type,
                    actor_id,
                    actor_role,
                    action,
                    target_type,
                    target_id,
                    payload_json,
                    ip_address,
                    prev_hash,
                    entry_hash,
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
        "(event_type, actor_id, actor_role, action, target_type, target_id, payload, "
        " ip_address, prev_hash, entry_hash) "
        "VALUES (%s, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb, %s, %s, %s) "
        "RETURNING id"
    )
    # CR-0166 R1-5：advisory lock 序列化（同 log_event）。caller 已在交易內時
    # transaction() 退化為 savepoint，鎖持有延至外層 commit（lock_timeout 2s 兜底）。
    async with db_module._conn.transaction():
        await _acquire_chain_lock()
        prev_hash, entry_hash, payload_json = await _chain_fields(
            event_type, actor_id, actor_role, action, target_type, target_id, payload
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
                payload_json,
                ip_address,
                prev_hash,
                entry_hash,
            ],
        )
        row = await cur.fetchone()
    return str(row[0])
