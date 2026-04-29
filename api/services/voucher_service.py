"""Voucher 業務邏輯。

範圍：listVouchers（cursor + limit + posting_date 區間）。
不含：exportVoucher（PDF 渲染由獨立模組 / 後續處理）。

DB↔OpenAPI 欄位對齊：
  - amount (NUMERIC) → string with pattern '^-?\\d+(\\.\\d{1,2})?$'：用 f"{x:.2f}"
  - currency 必傳 TWD（DB default）
  - related_entity_type 為 NULL 時不傳

租戶隔離：vouchers 自帶 tenant_id 欄位（與 manuals 同 pattern）。
"""

from __future__ import annotations

import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.voucher_service")


_SELECT_COLUMNS = (
    "id, voucher_number, related_entity_type, related_entity_id, "
    "debit_account, credit_account, amount, currency, "
    "posting_date, memo, created_at"
)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "voucher_number": row[1],
        "related_entity_type": row[2],
        "related_entity_id": str(row[3]) if row[3] else None,
        "debit_account": row[4],
        "credit_account": row[5],
        "amount": f"{float(row[6]):.2f}",
        "currency": row[7] or "TWD",
        "posting_date": row[8].isoformat() if row[8] else None,
        "memo": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
    }


async def list_vouchers(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    posting_date_start: date | None,
    posting_date_end: date | None,
) -> dict:
    if (
        posting_date_start is not None
        and posting_date_end is not None
        and posting_date_start > posting_date_end
    ):
        raise ApiError(
            "VALIDATION_ERROR",
            "posting_date_start must be <= posting_date_end",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if posting_date_start is not None:
        where.append("posting_date >= %s")
        args.append(posting_date_start)
    if posting_date_end is not None:
        where.append("posting_date <= %s")
        args.append(posting_date_end)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(posting_date, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM vouchers "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY posting_date DESC, id DESC "
        f"LIMIT %s"
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
        next_cursor = encode_cursor(
            {"ts": last[8].isoformat(), "id": str(last[0])}
        )

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
