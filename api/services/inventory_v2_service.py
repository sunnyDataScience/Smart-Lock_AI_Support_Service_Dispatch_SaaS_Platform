"""Inventory v2 業務邏輯 — per-tenant 庫存狀態機（FR-0007 / CR-0004 §8 / ADR-0052 / ADR-0053）。

範圍：
  - list_inventory_items_v2（cursor 分頁；stock_status/category/owner 過濾；讀 saas.inventory_item）
  - get_inventory_item_v2（單筆，404 NOT_FOUND）
  - create_inventory_item_v2（Idempotency-Key；建品項）
  - consume_material_v2（FR-0007 main flow：transaction + SELECT FOR UPDATE 扣庫存）
  - return_material_v2（transaction + 還原庫存）
  - restock_inventory_v2（transaction + 補貨）

設計決策（FR-0007 / CR-0004 §8 HD-INV-01~03 / ADR-0052 / ADR-0053）：
  - per-tenant 獨立倉（HD-INV-01）：saas.inventory_item 含 tenant_id，每租戶獨立。
  - owner enum（ADR-0052）：platform / brand / locksmith。
    注意：ADR-0052 frontmatter=accepted 但 body=Draft；業主授權按 Decision(推薦) 值開發。
  - serial_required（ADR-0053）：true 時 consume 未帶 serial → 422 SERIAL_REQUIRED。
  - HD-INV-03：consume vs material-request 語意留 owner 確認 + follow-up CR；
    本模組實作 FR-0007「領料扣庫存」，work_orders material-request 不動。
  - consume / return / restock 使用 transaction + SELECT FOR UPDATE（AC-05 並發 row-lock）。
    範式：async with db_module._conn.transaction(): SELECT ... FOR UPDATE; UPDATE; INSERT。
    autocommit conn 上開 BEGIN/COMMIT，對齊 auth_service.py:199 + work_order_service.py:236。
  - reorder 通知：consume 後若 quantity_on_hand < reorder_point → logger.info
    「InventoryBelowReorderPoint」（emit event 概念，MVP；warehouse_admin 通知 Phase II）。
  - serial 擋 WO complete：本波次不改 work_order_service（標 follow-up）。
  - stock_status 衍生（仿 legacy inventory_service）：
      out_of_stock：quantity_on_hand = 0
      low_stock：0 < quantity_on_hand <= reorder_point
      in_stock：quantity_on_hand > reorder_point
  - decimal（unit_cost）→ '%.2f' string（_coerce_decimal，仿 legacy dispute_service）。
  - brand_compatibility：text[] → Python list（_coerce_text_array）。
  - 不動 legacy inventory_service / public.inventory_items / public.inventory_transactions。
"""

from __future__ import annotations

import logging
import uuid as uuid_module

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.inventory_v2_service")

# ─────────────────────────────────────────────────────────────────────────────
# 常數
# ─────────────────────────────────────────────────────────────────────────────

_VALID_OWNER = {"platform", "brand", "locksmith"}

_VALID_STOCK_STATUS = {"out_of_stock", "low_stock", "in_stock"}

_VALID_TRANSACTION_TYPE = {"purchase", "consume", "return", "adjust"}

# ─────────────────────────────────────────────────────────────────────────────
# 型別強制轉換輔助
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_decimal(value) -> str | None:
    """numeric(12,2) → '%.2f' string；None → None（仿 legacy）。"""
    if value is None:
        return None
    return f"{float(value):.2f}"


def _coerce_text_array(raw) -> list[str] | None:
    """text[] → Python list；None → None。"""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# stock_status 衍生（仿 legacy inventory_service）
# ─────────────────────────────────────────────────────────────────────────────


def _derive_stock_status(qty: int, reorder: int) -> str:
    """衍生 stock_status：out_of_stock / low_stock / in_stock。"""
    if qty <= 0:
        return "out_of_stock"
    if qty <= reorder:
        return "low_stock"
    return "in_stock"


# ─────────────────────────────────────────────────────────────────────────────
# SELECT 欄位清單 & row → dict
# ─────────────────────────────────────────────────────────────────────────────

_ITEM_SELECT = (
    "i.id, i.tenant_id, i.part_number, i.name, i.category, "
    "i.brand_compatibility, i.unit_cost, i.quantity_on_hand, i.reorder_point, "
    "i.supplier, i.owner, i.serial_required, i.is_active, "
    "i.created_at, i.updated_at, "
    # UAT R3（契約 5）：last_restock_at = 該品項最近一筆 purchase 交易時間
    "(SELECT MAX(t.created_at) FROM saas.inventory_transaction t "
    " WHERE t.item_id = i.id AND t.transaction_type = 'purchase') AS last_restock_at"
)

# 欄位順序對齊 _ITEM_SELECT（16 欄）：
# [0]=id, [1]=tenant_id, [2]=part_number, [3]=name, [4]=category,
# [5]=brand_compatibility, [6]=unit_cost, [7]=quantity_on_hand, [8]=reorder_point,
# [9]=supplier, [10]=owner, [11]=serial_required, [12]=is_active,
# [13]=created_at, [14]=updated_at, [15]=last_restock_at（衍生）


def _row_to_item(row: tuple) -> dict:
    """row → item dict（帶衍生 stock_status / last_restock_at）。"""
    qty = int(row[7] or 0)
    reorder = int(row[8] or 0)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "part_number": row[2],
        "name": row[3],
        "category": row[4],
        "brand_compatibility": _coerce_text_array(row[5]),
        "unit_cost": _coerce_decimal(row[6]),
        "quantity_on_hand": qty,
        "reorder_point": reorder,
        "supplier": row[9],
        "owner": row[10] or "platform",
        "serial_required": bool(row[11]),
        "is_active": bool(row[12]),
        "stock_status": _derive_stock_status(qty, reorder),
        "created_at": row[13].isoformat() if row[13] else None,
        "updated_at": row[14].isoformat() if row[14] else None,
        # UAT R3（契約 5）：ISO|null——前端有值才渲染「最後補貨」
        "last_restock_at": row[15].isoformat() if row[15] else None,
    }


_TXN_SELECT = (
    "t.id, t.tenant_id, t.item_id, t.transaction_type, t.quantity, "
    "t.work_order_id, t.technician_id, t.serial, t.notes, t.created_at"
)

# [0]=id, [1]=tenant_id, [2]=item_id, [3]=transaction_type, [4]=quantity,
# [5]=work_order_id, [6]=technician_id, [7]=serial, [8]=notes, [9]=created_at


def _row_to_txn(row: tuple) -> dict:
    """row → transaction dict。"""
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "item_id": str(row[2]),
        "transaction_type": row[3],
        "quantity": int(row[4]),
        "work_order_id": str(row[5]) if row[5] else None,
        "technician_id": str(row[6]) if row[6] else None,
        "serial": row[7],
        "notes": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 公開 service functions
# ─────────────────────────────────────────────────────────────────────────────


async def list_inventory_items_v2(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    stock_status: str | None = None,
    category: str | None = None,
    owner: str | None = None,
    keyword: str | None = None,
) -> dict:
    """cursor 分頁列出 saas.inventory_item，tenant_id 直接過濾。

    stock_status 過濾（衍生）：對齊 legacy inventory_service SQL 條件。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if stock_status and stock_status not in _VALID_STOCK_STATUS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"stock_status must be one of {sorted(_VALID_STOCK_STATUS)}",
            422,
        )

    if owner and owner not in _VALID_OWNER:
        raise ApiError(
            "VALIDATION_ERROR",
            f"owner must be one of {sorted(_VALID_OWNER)}",
            422,
        )

    where = ["i.tenant_id = %s::uuid", "i.is_active = TRUE"]
    args: list = [tenant_id]

    # stock_status 過濾（對齊 legacy SQL 條件）
    if stock_status == "out_of_stock":
        where.append("i.quantity_on_hand = 0")
    elif stock_status == "low_stock":
        where.append("i.quantity_on_hand > 0 AND i.quantity_on_hand <= i.reorder_point")
    elif stock_status == "in_stock":
        where.append("i.quantity_on_hand > i.reorder_point")

    if category:
        where.append("i.category = %s")
        args.append(category)

    if owner:
        where.append("i.owner = %s")
        args.append(owner)

    if keyword:
        where.append(
            "(i.name ILIKE %s OR i.part_number ILIKE %s OR i.supplier ILIKE %s)"
        )
        like = f"%{keyword}%"
        args.extend([like, like, like])

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(i.created_at, i.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_ITEM_SELECT} FROM saas.inventory_item i "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY i.created_at DESC, i.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_item(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor({"ts": last[13].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_inventory_item_v2(*, tenant_id: str, item_id: str) -> dict:
    """單筆讀取，404 NOT_FOUND 若不存在或不屬於本 tenant。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_ITEM_SELECT} FROM saas.inventory_item i "
        f"WHERE i.id = %s::uuid AND i.tenant_id = %s::uuid",
        (item_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Inventory item {item_id} not found", 404)
    return _row_to_item(row)


async def create_inventory_item_v2(
    *,
    tenant_id: str,
    part_number: str,
    name: str,
    category: str | None = None,
    unit_cost: float | None = None,
    quantity_on_hand: int = 0,
    reorder_point: int = 0,
    supplier: str | None = None,
    owner: str = "platform",
    serial_required: bool = False,
) -> dict:
    """建立品項（status=active, owner=ADR-0052, serial_required=ADR-0053）。

    409 DUPLICATE_PART_NUMBER 若同 tenant part_number 已存在。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if owner not in _VALID_OWNER:
        raise ApiError(
            "VALIDATION_ERROR",
            f"owner must be one of {sorted(_VALID_OWNER)}",
            422,
        )

    if quantity_on_hand < 0:
        raise ApiError("VALIDATION_ERROR", "quantity_on_hand must be >= 0", 422)

    if reorder_point < 0:
        raise ApiError("VALIDATION_ERROR", "reorder_point must be >= 0", 422)

    item_id = str(uuid_module.uuid4())

    try:
        await db_module._conn.execute(
            "INSERT INTO saas.inventory_item "
            "  (id, tenant_id, part_number, name, category, unit_cost, "
            "   quantity_on_hand, reorder_point, supplier, owner, serial_required) "
            "VALUES "
            "  (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                item_id, tenant_id,
                part_number, name, category,
                unit_cost, quantity_on_hand, reorder_point,
                supplier, owner, serial_required,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 轉譯 unique violation 後原樣 re-raise
        err_str = str(exc).lower()
        if "unique" in err_str and "part_number" in err_str:
            raise ApiError(
                "DUPLICATE_PART_NUMBER",
                f"Part number '{part_number}' already exists for this tenant",
                409,
            ) from exc
        raise

    return await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)


async def consume_material_v2(
    *,
    tenant_id: str,
    item_id: str,
    quantity: int,
    work_order_id: str | None = None,
    technician_id: str | None = None,
    serial: str | None = None,
) -> dict:
    """FR-0007 main flow：領料扣庫存（transaction + SELECT FOR UPDATE）。

    AC-05 並發保護：
      BEGIN → SELECT quantity_on_hand FOR UPDATE（row-lock）
           → 檢查 quantity_on_hand >= quantity（否則 409 INSUFFICIENT_INVENTORY）
           → 檢查 serial_required（若 true 且無 serial → 422 SERIAL_REQUIRED）
           → UPDATE quantity_on_hand -= quantity
           → INSERT saas.inventory_transaction(consume)
      COMMIT

    reorder 通知：扣後 quantity_on_hand < reorder_point
      → logger.info「InventoryBelowReorderPoint」（emit event 概念，MVP；Phase II 通知 warehouse_admin）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if quantity <= 0:
        raise ApiError("VALIDATION_ERROR", "quantity must be > 0", 422)

    txn_id = str(uuid_module.uuid4())

    async with db_module._conn.transaction():
        # 1. row-lock：SELECT FOR UPDATE（AC-05 並發序列化）
        cur = await db_module._conn.execute(
            "SELECT quantity_on_hand, reorder_point, serial_required, is_active "
            "FROM saas.inventory_item "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid "
            "FOR UPDATE",
            (item_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Inventory item {item_id} not found", 404)

        qty_on_hand, reorder_point, serial_required, is_active = row

        if not is_active:
            raise ApiError("ITEM_INACTIVE", f"Inventory item {item_id} is inactive", 409)

        # 2. ADR-0053：serial_required 且缺 serial → 422
        if serial_required and not serial:
            raise ApiError(
                "SERIAL_REQUIRED",
                f"Item {item_id} requires a serial number for consume",
                422,
            )

        # 3. 庫存充足檢查（FR-0007 AC-05）
        if qty_on_hand < quantity:
            raise ApiError(
                "INSUFFICIENT_INVENTORY",
                f"Insufficient inventory: available={qty_on_hand}, requested={quantity}",
                409,
            )

        # 4. 扣庫存
        await db_module._conn.execute(
            "UPDATE saas.inventory_item "
            "SET quantity_on_hand = quantity_on_hand - %s "
            "WHERE id = %s::uuid",
            (quantity, item_id),
        )

        # 5. 記錄 ledger
        await db_module._conn.execute(
            "INSERT INTO saas.inventory_transaction "
            "  (id, tenant_id, item_id, transaction_type, quantity, "
            "   work_order_id, technician_id, serial) "
            "VALUES "
            "  (%s::uuid, %s::uuid, %s::uuid, 'consume', %s, "
            "   %s::uuid, %s::uuid, %s)",
            (
                txn_id, tenant_id, item_id, quantity,
                work_order_id, technician_id, serial,
            ),
        )

    # 6. reorder 通知（transaction 已 commit 後讀最新值）
    new_qty = qty_on_hand - quantity
    if new_qty < reorder_point:
        logger.info(
            "InventoryBelowReorderPoint: item_id=%s, tenant_id=%s, "
            "quantity_on_hand=%d, reorder_point=%d; "
            "Phase II: 通知 warehouse_admin",
            item_id, tenant_id, new_qty, reorder_point,
        )

    item = await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)
    txn_cur = await db_module._conn.execute(
        f"SELECT {_TXN_SELECT} FROM saas.inventory_transaction t WHERE t.id = %s::uuid",
        (txn_id,),
    )
    txn_row = await txn_cur.fetchone()
    txn = _row_to_txn(txn_row) if txn_row else None

    return {"item": item, "transaction": txn}


async def return_material_v2(
    *,
    tenant_id: str,
    item_id: str,
    quantity: int,
    work_order_id: str | None = None,
    technician_id: str | None = None,
    notes: str | None = None,
) -> dict:
    """還料：transaction + quantity_on_hand += quantity + INSERT transaction(return)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if quantity <= 0:
        raise ApiError("VALIDATION_ERROR", "quantity must be > 0", 422)

    txn_id = str(uuid_module.uuid4())

    async with db_module._conn.transaction():
        # row-lock
        cur = await db_module._conn.execute(
            "SELECT quantity_on_hand, is_active "
            "FROM saas.inventory_item "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid "
            "FOR UPDATE",
            (item_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Inventory item {item_id} not found", 404)

        _qty_on_hand, is_active = row

        if not is_active:
            raise ApiError("ITEM_INACTIVE", f"Inventory item {item_id} is inactive", 409)

        # 還料（+= quantity）
        await db_module._conn.execute(
            "UPDATE saas.inventory_item "
            "SET quantity_on_hand = quantity_on_hand + %s "
            "WHERE id = %s::uuid",
            (quantity, item_id),
        )

        # ledger
        await db_module._conn.execute(
            "INSERT INTO saas.inventory_transaction "
            "  (id, tenant_id, item_id, transaction_type, quantity, "
            "   work_order_id, technician_id, notes) "
            "VALUES "
            "  (%s::uuid, %s::uuid, %s::uuid, 'return', %s, "
            "   %s::uuid, %s::uuid, %s)",
            (
                txn_id, tenant_id, item_id, quantity,
                work_order_id, technician_id, notes,
            ),
        )

    item = await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)
    txn_cur = await db_module._conn.execute(
        f"SELECT {_TXN_SELECT} FROM saas.inventory_transaction t WHERE t.id = %s::uuid",
        (txn_id,),
    )
    txn_row = await txn_cur.fetchone()
    txn = _row_to_txn(txn_row) if txn_row else None

    return {"item": item, "transaction": txn}


async def restock_inventory_v2(
    *,
    tenant_id: str,
    item_id: str,
    quantity: int,
    supplier: str | None = None,
    notes: str | None = None,
) -> dict:
    """補貨：transaction + quantity_on_hand += quantity + INSERT transaction(purchase)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if quantity <= 0:
        raise ApiError("VALIDATION_ERROR", "quantity must be > 0", 422)

    txn_id = str(uuid_module.uuid4())

    async with db_module._conn.transaction():
        # row-lock
        cur = await db_module._conn.execute(
            "SELECT quantity_on_hand, is_active "
            "FROM saas.inventory_item "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid "
            "FOR UPDATE",
            (item_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Inventory item {item_id} not found", 404)

        _qty_on_hand, is_active = row

        if not is_active:
            raise ApiError("ITEM_INACTIVE", f"Inventory item {item_id} is inactive", 409)

        # 補貨（+= quantity）
        await db_module._conn.execute(
            "UPDATE saas.inventory_item "
            "SET quantity_on_hand = quantity_on_hand + %s, "
            "    supplier = COALESCE(%s, supplier) "
            "WHERE id = %s::uuid",
            (quantity, supplier, item_id),
        )

        # ledger
        await db_module._conn.execute(
            "INSERT INTO saas.inventory_transaction "
            "  (id, tenant_id, item_id, transaction_type, quantity, notes) "
            "VALUES "
            "  (%s::uuid, %s::uuid, %s::uuid, 'purchase', %s, %s)",
            (txn_id, tenant_id, item_id, quantity, notes),
        )

    item = await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)
    txn_cur = await db_module._conn.execute(
        f"SELECT {_TXN_SELECT} FROM saas.inventory_transaction t WHERE t.id = %s::uuid",
        (txn_id,),
    )
    txn_row = await txn_cur.fetchone()
    txn = _row_to_txn(txn_row) if txn_row else None

    return {"item": item, "transaction": txn}


# ─────────────────────────────────────────────────────────────────────────────
# update_inventory_item_v2 — PATCH 部分更新（不動 quantity_on_hand）
# ─────────────────────────────────────────────────────────────────────────────

async def update_inventory_item_v2(
    *,
    tenant_id: str,
    item_id: str,
    patch: dict,
) -> dict:
    """PATCH /tenants/{tid}/inventory/items/{itemId}.

    允許更新欄位: name / category / unit_cost / reorder_point / supplier /
    owner / serial_required. 不允許動 quantity_on_hand (走 :restock/:consume).
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    allowed = {
        "name", "category", "unit_cost", "reorder_point",
        "supplier", "owner", "serial_required",
    }
    sets: list[str] = []
    args: list = []
    for k, v in patch.items():
        if k not in allowed:
            continue
        if v is None and k in ("name",):
            continue
        sets.append(f"{k} = %s")
        args.append(v)

    if not sets:
        # nothing to update — 直接回現有
        return await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)

    args.extend([item_id, tenant_id])
    sql = (
        f"UPDATE saas.inventory_item "
        f"SET {', '.join(sets)} "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, args)
    if cur.rowcount == 0:
        raise ApiError("NOT_FOUND", f"Inventory item {item_id} not found", 404)

    return await get_inventory_item_v2(tenant_id=tenant_id, item_id=item_id)


# ─────────────────────────────────────────────────────────────────────────────
# list_inventory_transactions_v2 — GET ledger (item 異動紀錄)
# ─────────────────────────────────────────────────────────────────────────────

async def list_inventory_transactions_v2(
    *,
    tenant_id: str,
    item_id: str | None = None,
    transaction_type: str | None = None,
    limit: int = 50,
) -> dict:
    """GET /tenants/{tid}/inventory/transactions

    Filter by item_id + transaction_type. 按 created_at DESC.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["t.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if item_id:
        where.append("t.item_id = %s::uuid")
        args.append(item_id)

    if transaction_type:
        if transaction_type not in {"purchase", "consume", "return", "adjust"}:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid transaction_type: {transaction_type}",
                422,
            )
        where.append("t.transaction_type = %s")
        args.append(transaction_type)

    sql = (
        f"SELECT {_TXN_SELECT} FROM saas.inventory_transaction t "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY t.created_at DESC "
        f"LIMIT %s"
    )
    args.append(limit)

    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()
    return {"items": [_row_to_txn(r) for r in rows]}
