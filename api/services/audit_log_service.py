"""Audit Log 業務邏輯。

讀 `audit_events` 表（Schema_v2_extensions.sql 的結構化稽核事件表），
mapping 成 OpenAPI `AuditLogEntry` schema：
  - event_type → log_type（enum 不在白名單時 fallback 'admin_action'）
  - actor_id / action / payload(→details) / created_at 直接對應

audit_events 沒有 tenant_id 欄。

⚠️ 上面那句原本接「本期不做 tenant 過濾（audit 為部署層級事件）」——**該敘述已過期**。
CR-0183（跨面 RBAC 收斂）的方向是逐端點收緊可見範圍，而 audit list/export 兩個端點
目前仍讓任何後台角色讀到**全部租戶**的稽核事件。這是 CR-0207 D1 的待裁決項
（(a) 補 tenant_id 欄但 backfill 需繞過 append-only 防護 / (b) 先收緊角色止血）。
在裁決前不要把這句話當成「設計如此」——它只是還沒處理。
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
    # CR-0166 R1-8：payload 自由文字欄（reason/notes/email 等）入庫＋入 hash 前先
    # 遮蔽高置信 PII（email/電話/身分證/LINE uid，不含地址啟發式以保稽核證據力）。
    # 在 json.dumps 與 hash 之前——hash 鏈事後不可改。
    if payload:
        from core.pii_scrub import scrub_audit_payload
        payload = scrub_audit_payload(payload)
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    payload_canon = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else None
    )
    prev_hash = await _latest_entry_hash()
    content = _canonical_audit_content(
        event_type, actor_id, actor_role, action, target_type, target_id, payload_canon
    )
    return prev_hash, _compute_entry_hash(prev_hash, content), payload_json


async def get_latest_checkpoint() -> dict | None:
    """取最新 re-baseline checkpoint（CR-0184）；無則 None。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, baseline_entry_hash, baseline_row_id, baseline_created_at, note, created_at "
        "FROM audit_chain_checkpoint ORDER BY created_at DESC, id DESC LIMIT 1"
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "baseline_entry_hash": row[1],
        "baseline_row_id": str(row[2]) if row[2] else None,
        "baseline_created_at": row[3].isoformat() if row[3] else None,
        "note": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


async def create_chain_checkpoint(*, note: str | None = None, created_by: str | None = None) -> dict:
    """建 re-baseline checkpoint（CR-0184）：以目前鏈末（最新 entry_hash）為新基準。

    在鏈 advisory lock 內快照鏈末，確保基準列與其後不會被同時寫入的新事件插隊。
    verify(use_checkpoint=True) 之後只驗此基準列「之後」的鏈段——歷史（含 pre-CR-0166
    並發分叉）保留不刪、視為凍結基準。用於在歷史斷鏈下重建往後可驗證的乾淨鏈。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    async with db_module._conn.transaction():
        await _acquire_chain_lock()
        cur = await db_module._conn.execute(
            "SELECT id, entry_hash, created_at FROM audit_events "
            "WHERE entry_hash IS NOT NULL ORDER BY created_at DESC, id DESC LIMIT 1"
        )
        tip = await cur.fetchone()
        baseline_hash = tip[1] if tip else _AUDIT_GENESIS
        baseline_id = tip[0] if tip else None
        baseline_at = tip[2] if tip else None
        ins = await db_module._conn.execute(
            "INSERT INTO audit_chain_checkpoint "
            "(baseline_entry_hash, baseline_row_id, baseline_created_at, note, created_by) "
            "VALUES (%s, %s, %s, %s, %s::uuid) RETURNING id, created_at",
            (baseline_hash, baseline_id, baseline_at, note, created_by),
        )
        cp = await ins.fetchone()
    return {
        "id": str(cp[0]),
        "baseline_entry_hash": baseline_hash,
        "baseline_row_id": str(baseline_id) if baseline_id else None,
        "baseline_created_at": baseline_at.isoformat() if baseline_at else None,
        "note": note,
        "created_at": cp[1].isoformat() if cp[1] else None,
    }


async def verify_audit_chain(*, limit: int = 1000, use_checkpoint: bool = True) -> dict:
    """驗證 audit hash chain 完整性（只驗有 entry_hash 的鏈段，依時序）。

    偵測兩類竄改：(1) 列內容被改 → entry_hash 重算不符；(2) 列被刪/插/分叉 →
    prev_hash 不接前一列。CR-0184 增強：
      - use_checkpoint（預設 True）：有 re-baseline checkpoint 時，只驗基準列「之後」
        的鏈段（expected_prev 從 baseline_entry_hash 起）；歷史凍結不驗。
      - 回報**所有**斷點（breaks 陣列），非只第一個；遇斷後 resync（以該列 entry_hash
        為新起點續驗）以找出後續斷點。broken_at 保留為第一個斷點（向下相容）。
    回 {checked, valid, broken_at, breaks:[...], checkpoint:{...}|None}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    checkpoint = await get_latest_checkpoint() if use_checkpoint else None
    where = "entry_hash IS NOT NULL"
    args: list = []
    expected_prev = _AUDIT_GENESIS
    if checkpoint and checkpoint["baseline_created_at"]:
        # 只驗基準列「之後」：(created_at, id) > (baseline_created_at, baseline_row_id)
        where += " AND (created_at, id) > (%s::timestamptz, %s::uuid)"
        args.extend([checkpoint["baseline_created_at"], checkpoint["baseline_row_id"]])
        expected_prev = checkpoint["baseline_entry_hash"]

    cur = await db_module._conn.execute(
        "SELECT id, event_type, actor_id, actor_role, action, target_type, target_id, "
        "       payload, prev_hash, entry_hash "
        f"FROM audit_events WHERE {where} "
        "ORDER BY created_at ASC, id ASC LIMIT %s",
        (*args, limit),
    )
    rows = await cur.fetchall()
    checked = 0
    breaks: list[str] = []
    for r in rows:
        checked += 1
        payload_json = json.dumps(r[7], ensure_ascii=False, sort_keys=True) if r[7] is not None else None
        content = _canonical_audit_content(
            r[1], str(r[2]) if r[2] else None, r[3], r[4], r[5],
            str(r[6]) if r[6] else None, payload_json,
        )
        recomputed = _compute_entry_hash(r[8] or _AUDIT_GENESIS, content)
        if recomputed != r[9] or (r[8] or _AUDIT_GENESIS) != expected_prev:
            breaks.append(str(r[0]))
        # resync：以本列 entry_hash 為後續 expected_prev（斷後續驗，找出所有斷點）
        expected_prev = r[9]
    return {
        "checked": checked,
        "valid": len(breaks) == 0,
        "broken_at": breaks[0] if breaks else None,
        "breaks": breaks,
        "checkpoint": checkpoint,
    }


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
