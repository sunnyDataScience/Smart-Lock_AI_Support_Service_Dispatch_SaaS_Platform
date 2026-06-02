"""Dispatch Logs 業務邏輯（Phase 1.26 read-only）。

範圍：listDispatchLogs（cursor + limit + work_order_id + action）。
不含 write 路徑；dispatch_logs 由 AI 派工引擎與工單寫入流程在背景產生。

OpenAPI DispatchLog schema：
    id, work_order_id, action (6 enum), created_at；
    optional: technician_id, technician_name, match_score, match_factors (jsonb),
    rejection_reason, timeout_seconds, notes.

DB ↔ API 對齊：
  - dispatch_logs.action (varchar(50))   → API DispatchAction；非預期值視為 assign
  - match_score (FLOAT)                  → 直通 number；NULL → None
  - match_factors (jsonb)                → 直通；NULL → None
  - technicians.name                     → JOIN 取為 technician_name 方便前端顯示

租戶隔離：dispatch_logs 沒 tenant_id，透過
    JOIN work_orders → problem_cards → conversations → users
延伸 4 層 JOIN 取 users.tenant_id 過濾（與 refund_service 同 pattern）。
"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.dispatch_log_service")


_VALID_ACTIONS = {"assign", "accept", "reject", "timeout", "reassign", "cancel"}


def _coerce_action(raw: str | None) -> str:
    if raw and raw in _VALID_ACTIONS:
        return raw
    return "assign"


def _coerce_factors(raw):
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "work_order_id": str(row[1]),
        "action": _coerce_action(row[2]),
        "technician_id": str(row[3]) if row[3] else None,
        "technician_name": row[4],
        "match_score": float(row[5]) if row[5] is not None else None,
        "match_factors": _coerce_factors(row[6]),
        "rejection_reason": row[7],
        "timeout_seconds": int(row[8]) if row[8] is not None else None,
        "notes": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
    }


_SELECT = (
    "dl.id, dl.work_order_id, dl.action, dl.technician_id, t.name AS technician_name, "
    "dl.match_score, dl.match_factors, dl.rejection_reason, dl.timeout_seconds, "
    "dl.notes, dl.created_at"
)

_TENANT_JOIN = (
    "FROM dispatch_logs dl "
    "LEFT JOIN technicians t ON dl.technician_id = t.id "
    "JOIN work_orders wo ON dl.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "JOIN conversations c ON pc.conversation_id = c.id "
    "JOIN users u ON c.user_id = u.id"
)


async def list_dispatch_logs(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    work_order_id: str | None = None,
    action: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if work_order_id:
        where.append("dl.work_order_id = %s::uuid")
        args.append(work_order_id)

    if action:
        if action not in _VALID_ACTIONS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid action filter: {action}",
                422,
            )
        where.append("dl.action = %s")
        args.append(action)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(dl.created_at, dl.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY dl.created_at DESC, dl.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_dict(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor({"ts": last[10].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_dispatch_log(*, tenant_id: str, log_id: str) -> dict:
    """取單筆 dispatch log，透過 tenant JOIN 隔離（v2 get-by-id）。

    同 list_dispatch_logs，租戶隔離走
        dispatch_logs → work_orders → problem_cards → conversations → users
    四層 JOIN 確保跨租戶無法讀取他人日誌。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE dl.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (log_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"DispatchLog {log_id} not found", 404)
    return _row_to_dict(row)
