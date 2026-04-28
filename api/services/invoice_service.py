"""Invoices 業務邏輯（Phase 1.21 read-only）。

範圍：listInvoices（cursor + limit + status + work_order_id）、getInvoice。
不含：createInvoice / voidInvoice / reissueInvoice / 折讓寫入路徑。

OpenAPI Invoice schema：
    id, work_order_id, invoice_number, amount (decimal str), status (5 enum),
    issued_at, created_at, updated_at; tax_id?, tax_type?, voided_at?,
    void_reason?, allowance_amount?, category?, reopened_from?

DB ↔ API 對齊：
  - invoices.amount (FLOAT)        → API amount: decimal string with 2 decimals
  - invoices.status (4 值)         → API InvoiceStatus（5 enum）mapping：
        draft     → pending
        issued    → issued
        paid      → issued      （API 無 paid 狀態，視為已開立完成）
        cancelled → voided
  - invoices.tax / total / line_items → DB only，不外洩
  - tax_id / tax_type / category / allowance_amount / reopened_from
        → 目前 DB 無欄位，全部不傳（optional）

租戶隔離：invoices 沒有 tenant_id，透過
    JOIN work_orders → problem_cards → conversations → users
延伸 4 層 JOIN 取 users.tenant_id 過濾（與 work_order_service 同 pattern）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.invoice_service")


_VALID_STATUS_FILTER = {"pending", "issued", "allowance_pending", "voided", "reopened"}

_DB_STATUS_TO_API = {
    "draft": "pending",
    "issued": "issued",
    "paid": "issued",
    "cancelled": "voided",
}

_API_STATUS_TO_DB_FILTER: dict[str, list[str]] = {
    "pending": ["draft"],
    "issued": ["issued", "paid"],
    "voided": ["cancelled"],
    "allowance_pending": [],
    "reopened": [],
}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT：
    i.id, i.work_order_id, i.invoice_number, i.amount, i.status,
    i.issued_at, i.created_at, i.updated_at
    """
    out: dict = {
        "id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "invoice_number": row[2] or "",
        "amount": _coerce_decimal(row[3]),
        "status": _DB_STATUS_TO_API.get(row[4] or "draft", "pending"),
        "issued_at": row[5].isoformat() if row[5] else (row[6].isoformat() if row[6] else None),
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }
    return out


_SELECT = (
    "i.id, i.work_order_id, i.invoice_number, i.amount, i.status, "
    "i.issued_at, i.created_at, i.updated_at"
)

_TENANT_JOIN = (
    "FROM invoices i "
    "JOIN work_orders wo ON i.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "JOIN conversations c ON pc.conversation_id = c.id "
    "JOIN users u ON c.user_id = u.id"
)


async def list_invoices(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_STATUS_FILTER:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        db_values = _API_STATUS_TO_DB_FILTER.get(status, [])
        if not db_values:
            return {"items": [], "next_cursor": None, "has_more": False}
        placeholders = ", ".join(["%s"] * len(db_values))
        where.append(f"i.status IN ({placeholders})")
        args.extend(db_values)

    if work_order_id:
        where.append("i.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(i.created_at, i.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY i.created_at DESC, i.id DESC "
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
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_invoice(*, tenant_id: str, invoice_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE i.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (invoice_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Invoice {invoice_id} not found", 404)
    return _row_to_dict(row)
