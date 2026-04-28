"""Settlements 業務邏輯（Phase 1.13 read-only）。

範圍：listSettlements（cursor + limit + status + technician_id 篩選）。
不含：approveReconciliation / submitRefundDecision / 對帳寫入路徑。

OpenAPI Settlement schema：
    id, reconciliation_id, technician_id, technician_name?, amount (decimal str),
    currency (TWD), status (pending|paid|failed), payment_method?, paid_at?, created_at

DB ↔ API 對齊：
  - settlements.amount (FLOAT) → API amount: decimal string with 2 decimals
  - settlements.currency        → 直通；DB 保留 NULL fallback 為 'TWD'
  - settlements.status (pending|paid|failed) → 直通（DB 三值與 API enum 完全一致）
  - settlements.payment_method (bank_transfer|other) → 直通
  - technicians.name JOIN 取出 → API technician_name

租戶隔離：settlements 沒有 tenant_id；透過 JOIN technicians ON tenant_id 過濾。
所有結算列都必須對應一位 technician（DB FK NOT NULL on FK ref，但實務上 ON DELETE
RESTRICT 會擋住孤兒列），所以 INNER JOIN 安全。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.settlement_service")


_VALID_STATUS = {"pending", "paid", "failed"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序：
    s.id, s.reconciliation_id, s.technician_id, s.amount, s.currency,
    s.status, s.payment_method, s.paid_at, s.created_at, t.name
    """
    out: dict = {
        "id": str(row[0]),
        "reconciliation_id": str(row[1]),
        "technician_id": str(row[2]),
        "amount": _coerce_decimal(row[3]),
        "currency": (row[4] or "TWD"),
        "status": row[5] or "pending",
        "created_at": row[8].isoformat() if row[8] else None,
    }
    if row[9]:
        out["technician_name"] = row[9]
    if row[6]:
        out["payment_method"] = row[6]
    if row[7] is not None:
        out["paid_at"] = row[7].isoformat()
    return out


_SELECT = (
    "s.id, s.reconciliation_id, s.technician_id, s.amount, s.currency, "
    "s.status, s.payment_method, s.paid_at, s.created_at, t.name"
)

_JOIN = (
    "FROM settlements s "
    "JOIN technicians t ON s.technician_id = t.id"
)


async def list_settlements(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    technician_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["t.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("s.status = %s")
        args.append(status)

    if technician_id:
        where.append("s.technician_id = %s::uuid")
        args.append(technician_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(s.created_at, s.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY s.created_at DESC, s.id DESC "
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
        next_cursor = encode_cursor({"ts": last[8].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
