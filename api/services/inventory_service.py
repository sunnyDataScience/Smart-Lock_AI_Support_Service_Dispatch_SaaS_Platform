"""Inventory 業務邏輯（read-only 庫存品項）。

讀 inventory_items 表（is_active=TRUE），衍生欄位：
  - stock_status：依 quantity_on_hand vs reorder_point 計算
      out_of_stock：quantity_on_hand = 0
      low_stock：0 < quantity_on_hand <= reorder_point
      in_stock：quantity_on_hand > reorder_point
  - last_restocked_at：MAX(created_at) FROM inventory_transactions WHERE transaction_type='purchase'

注意：inventory_items 是全公司共用倉庫表（無 tenant_id 欄位），所有租戶看到相同庫存。
此設計來自 SQL/Schema_v2_extensions.sql GAP #17，本 phase 維持原狀，
未來若改為 per-tenant 倉庫需 schema migration。

Cursor: (created_at, id) 倒序。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.inventory_service")


_ITEM_SELECT = """
    i.id,
    i.part_number,
    i.name,
    i.category,
    i.brand_compatibility,
    i.unit_cost,
    i.quantity_on_hand,
    i.reorder_point,
    i.supplier,
    i.is_active,
    i.created_at,
    i.updated_at,
    (
        SELECT MAX(t.created_at) FROM inventory_transactions t
        WHERE t.item_id = i.id AND t.transaction_type = 'purchase'
    ) AS last_restocked_at
"""


def _derive_stock_status(qty: int, reorder: int) -> str:
    if qty <= 0:
        return "out_of_stock"
    if qty <= reorder:
        return "low_stock"
    return "in_stock"


def _coerce_decimal(value) -> str | None:
    if value is None:
        return None
    return f"{float(value):.2f}"


def _row_to_item(row: tuple) -> dict:
    qty = int(row[6] or 0)
    reorder = int(row[7] or 0)
    return {
        "id": str(row[0]),
        "part_number": row[1],
        "name": row[2],
        "category": row[3],
        "brand_compatibility": row[4] if row[4] else None,
        "unit_cost": _coerce_decimal(row[5]),
        "quantity_on_hand": qty,
        "reorder_point": reorder,
        "supplier": row[8],
        "is_active": bool(row[9]),
        "stock_status": _derive_stock_status(qty, reorder),
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
        "last_restocked_at": row[12].isoformat() if row[12] else None,
    }


async def list_items(
    *,
    cursor: str | None,
    limit: int,
    stock_status: str | None,
    category: str | None,
) -> dict:
    """GET /inventory/items — cursor 分頁；stock_status / category 可選過濾。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["i.is_active = TRUE"]
    args: list = []

    if stock_status == "out_of_stock":
        where.append("i.quantity_on_hand = 0")
    elif stock_status == "low_stock":
        where.append("i.quantity_on_hand > 0 AND i.quantity_on_hand <= i.reorder_point")
    elif stock_status == "in_stock":
        where.append("i.quantity_on_hand > i.reorder_point")

    if category:
        where.append("i.category = %s")
        args.append(category)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(i.created_at, i.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_ITEM_SELECT} FROM inventory_items i "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY i.created_at DESC, i.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_item(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[10].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
