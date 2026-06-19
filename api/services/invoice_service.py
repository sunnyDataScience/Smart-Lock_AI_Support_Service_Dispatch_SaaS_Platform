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

import json
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
    keyword: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    payment_method: str | None = None,
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

    if keyword:
        where.append("i.invoice_number ILIKE %s")
        args.append(f"%{keyword}%")

    if created_after:
        where.append("i.created_at >= %s::timestamptz")
        args.append(created_after)

    if created_before:
        where.append("i.created_at <= %s::timestamptz")
        args.append(created_before)

    if payment_method:
        if payment_method not in {
            "credit_card", "bank_transfer", "cash", "line_pay", "other",
        }:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid payment_method: {payment_method}",
                422,
            )
        where.append("i.payment_method = %s")
        args.append(payment_method)

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


def _gen_invoice_number(work_order_id: str) -> str:
    """發票號（mock-first）：IV + 8 數字，符合 Invoice schema 規範 `^[A-Z]{2}\\d{8}$`。

    8 數字取 uuid 整數 mod 10^8；唯一性由 invoices.invoice_number UNIQUE 約束最終保證
    （碰撞機率 ~1/10^8，極低）。正式發票字軌/序列規則待 esales（§8 Q-3）。
    """
    import uuid as _uuid
    return f"IV{_uuid.uuid4().int % 100_000_000:08d}"


# 訂金 fallback（config 缺失時；對齊 esales sheet24 CFG-DEPOSIT-RATE/MIN）
_DEPOSIT_RATE_FALLBACK = 0.3
_DEPOSIT_MIN_FALLBACK = 1000.0


async def _resolve_deposit(amount: float) -> float:
    """從 deposit_policy config 算訂金（CR-0036）：round(min(amount, max(amount×rate, min_twd)), 2)。

    即「rate/min 取高，但不超過 total」。值走 M18 config 治理（sheet 24「不可寫死」）；
    config 缺失或壞值 → fallback 常數（不破，並 logger.warning 可追蹤 fallback 觸發）。
    amount ≤ 0 → 0（守會計不變式，不產生負/誤訂金）。
    """
    from services import config_m18_service
    cfg = await config_m18_service.read_global_value(namespace="deposit_policy")
    if not cfg:
        logger.warning("deposit_policy config missing — fallback rate=%.2f min=%.0f",
                       _DEPOSIT_RATE_FALLBACK, _DEPOSIT_MIN_FALLBACK)
        cfg = {}
    try:
        rate = float(cfg.get("rate", _DEPOSIT_RATE_FALLBACK))
        min_twd = float(cfg.get("min_twd", _DEPOSIT_MIN_FALLBACK))
    except (ValueError, TypeError):
        logger.warning("deposit_policy config malformed (%r) — using fallback", cfg)
        rate, min_twd = _DEPOSIT_RATE_FALLBACK, _DEPOSIT_MIN_FALLBACK
    if amount <= 0:
        return 0.0
    return round(min(amount, max(amount * rate, min_twd)), 2)


async def create_from_quote(*, tenant_id: str, quote_id: str) -> dict:
    """從 accepted 報價開立客戶應收發票（CR-0035，mock-first）。

    冪等：invoices.work_order_id UNIQUE + INSERT ON CONFLICT DO NOTHING —— 並發/重複呼叫
    皆回既有發票（race-safe，不丟 UNIQUE 例外）。
    金額取報價客戶價（不含內部成本 unit_price）；稅 mock 0（待 esales Q-07）；is_mock 沿報價旗標。
    line_items 結構：[{item_name, category, quantity, customer_price}] —— **不含 unit_price**（成本不外洩）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 取報價（嚴格限本租戶；財務寫入不容 tenant_id IS NULL 鬆綁）+ 客戶價明細
    q = await (await db_module._conn.execute(
        "SELECT id, work_order_id, state, total_amount, is_mock FROM quote "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (quote_id, tenant_id))).fetchone()
    if not q:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if q[1] is None:
        raise ApiError("VALIDATION_ERROR", "quote has no work_order to bill", 422)
    if q[2] != "accepted":
        raise ApiError("STATE_CONFLICT", f"cannot invoice quote in '{q[2]}' (must be accepted)", 409)
    if q[3] is None or float(q[3]) <= 0:
        raise ApiError("VALIDATION_ERROR", "quote has no billable amount (no line items)", 422)
    work_order_id = str(q[1])

    # 客戶價明細（不含 unit_price 內部成本）
    line_rows = await (await db_module._conn.execute(
        "SELECT item_name, category, quantity, customer_price FROM quote_line_items "
        "WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    line_items = [{
        "item_name": r[0], "category": r[1], "quantity": int(r[2]),
        "customer_price": _coerce_decimal(r[3]),
    } for r in line_rows]

    amount = float(q[3])
    tax = 0.0  # mock：未稅（待 esales Q-07）
    total = amount + tax
    deposit_required = await _resolve_deposit(total)  # CR-0036：從 deposit_policy config 算
    invoice_number = _gen_invoice_number(work_order_id)
    is_mock = bool(q[4])

    # 原子冪等：work_order_id UNIQUE 衝突 → DO NOTHING（不丟例外）→ RETURNING 為空 → 回既有
    row = await (await db_module._conn.execute(
        "INSERT INTO invoices (work_order_id, quote_id, invoice_number, amount, tax, total, "
        "  status, line_items, issued_at, is_mock, deposit_required) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, 'issued', %s::jsonb, NOW(), %s, %s) "
        "ON CONFLICT (work_order_id) DO NOTHING RETURNING id",
        (work_order_id, quote_id, invoice_number, amount, tax, total,
         json.dumps(line_items, ensure_ascii=False), is_mock, deposit_required))).fetchone()
    if row is None:
        # 已有發票（並發或重複 accept）→ 回既有，不重開
        existing = await (await db_module._conn.execute(
            "SELECT id FROM invoices WHERE work_order_id = %s::uuid", (work_order_id,))).fetchone()
        logger.info("invoice already exists for wo=%s (idempotent return)", work_order_id)
        return await get_invoice(tenant_id=tenant_id, invoice_id=str(existing[0]))
    logger.info("invoice created from quote: invoice=%s quote=%s wo=%s amount=%.2f mock=%s",
                row[0], quote_id, work_order_id, amount, is_mock)
    return await get_invoice(tenant_id=tenant_id, invoice_id=str(row[0]))


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
