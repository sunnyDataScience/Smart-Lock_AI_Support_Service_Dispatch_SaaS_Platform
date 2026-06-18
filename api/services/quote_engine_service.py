"""CR-0032 報價引擎 service（Phase A）。

報價主表狀態機 + 從 CR-0034 catalog 帶價 + 送客戶凍結 snapshot。
數值走 mock 主檔（CR-0034 / 決議 5）；核准門檻/訂金/正式價待 esales Q-01~Q-12。

狀態機：draft → pending_approval → approved → sent → accepted | rejected | expired | superseded
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.quote_engine_service")

# 允許的狀態轉換（action → (from_states, to_state)）
_TRANSITIONS = {
    "submit":  ({"draft"}, "pending_approval"),
    "approve": ({"pending_approval"}, "approved"),
    "reject":  ({"pending_approval"}, "rejected"),
    "send":    ({"approved", "draft"}, "sent"),  # draft 可直送（免核門檻內，門檻 esales Q-11 待定）
    "accept":  ({"sent"}, "accepted"),
    "decline": ({"sent"}, "rejected"),
}

# 有效期（BR-M04-05）：一般 14d、急件 3d
_VALIDITY_DAYS_NORMAL = 14
_VALIDITY_DAYS_URGENT = 3

# 核准門檻（mock 預設；正式值待業主 esales Q-11）：總額超此值不可從 draft 直送，須先核准
_APPROVAL_THRESHOLD = 10000.0


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


async def create_quote(
    *, tenant_id: str, work_order_id: str, created_by: str | None = None,
    urgent: bool = False,
) -> dict:
    """從 work_order 建 draft 報價（version 1，有效期 BR-M04-05）。"""
    conn = await _conn()
    # 取 problem_card_id（沿 work_order）
    pc = await (await conn.execute(
        "SELECT problem_card_id FROM work_orders WHERE id = %s::uuid", (work_order_id,)
    )).fetchone()
    if not pc:
        raise ApiError("NOT_FOUND", "work order not found", 404)
    days = _VALIDITY_DAYS_URGENT if urgent else _VALIDITY_DAYS_NORMAL
    expiry = datetime.now(timezone.utc) + timedelta(days=days)
    row = await (await conn.execute(
        "INSERT INTO quote (work_order_id, problem_card_id, state, expiry_at, tenant_id, created_by) "
        "VALUES (%s::uuid, %s, 'draft', %s, %s::uuid, %s) RETURNING id",
        (work_order_id, pc[0], expiry, tenant_id, created_by),
    )).fetchone()
    return await get_quote(quote_id=str(row[0]), tenant_id=tenant_id, include_cost=True)


async def add_line(
    *, tenant_id: str, quote_id: str, quantity: int = 1,
    service_code: str | None = None, material_code: str | None = None,
    item_name: str | None = None,
) -> dict:
    """加一筆報價項，價格從 CR-0034 catalog 帶（mock）。"""
    conn = await _conn()
    q = await (await conn.execute("SELECT state, work_order_id FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not q:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if q[0] not in ("draft", "pending_approval"):
        raise ApiError("STATE_CONFLICT", f"cannot add line to quote in '{q[0]}'", 409)

    if service_code:
        cat = await (await conn.execute(
            "SELECT service_name, internal_base_cost, suggested_customer_price, 'labor' "
            "FROM service_catalog WHERE service_code = %s", (service_code,))).fetchone()
        category = "labor"
    elif material_code:
        cat = await (await conn.execute(
            "SELECT material_name, internal_cost, suggested_price, 'material' "
            "FROM material_catalog WHERE material_code = %s", (material_code,))).fetchone()
        category = "material"
    else:
        raise ApiError("VALIDATION_ERROR", "service_code or material_code required", 422)
    if not cat:
        raise ApiError("NOT_FOUND", "catalog item not found", 404)

    name = item_name or cat[0]
    unit_cost = cat[1] or 0
    cust_price = cat[2] or 0
    await conn.execute(
        "INSERT INTO quote_line_items (quote_id, work_order_id, tenant_id, item_name, category, "
        "  unit_price, quantity, customer_price, is_mock, service_code, material_code) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, TRUE, %s, %s)",
        (quote_id, q[1], tenant_id, name, category, unit_cost, quantity, cust_price,
         service_code, material_code),
    )
    await _recompute_total(quote_id)
    return await get_quote(quote_id=quote_id, tenant_id=tenant_id, include_cost=True)


async def _recompute_total(quote_id: str) -> None:
    conn = await _conn()
    total = (await (await conn.execute(
        "SELECT COALESCE(SUM(customer_price * quantity), 0) FROM quote_line_items WHERE quote_id = %s::uuid",
        (quote_id,))).fetchone())[0]
    await conn.execute(
        "UPDATE quote SET total_amount = %s, updated_at = NOW() WHERE id = %s::uuid", (total, quote_id))


async def get_quote(*, tenant_id: str, quote_id: str, include_cost: bool) -> dict:
    conn = await _conn()
    r = await (await conn.execute(
        "SELECT id, work_order_id, version, state, total_amount, deposit_required, "
        "       expiry_at, snapshot_hash, is_mock, created_at "
        "FROM quote WHERE id = %s::uuid AND (tenant_id = %s::uuid OR tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone()
    if not r:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    lines_rows = await (await conn.execute(
        "SELECT id, item_name, category, unit_price, quantity, customer_price, service_code, material_code "
        "FROM quote_line_items WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    lines = []
    for lr in lines_rows:
        line = {"id": str(lr[0]), "item_name": lr[1], "category": lr[2], "quantity": int(lr[4]),
                "customer_price": _dec(lr[5]), "service_code": lr[6], "material_code": lr[7]}
        if include_cost:
            line["unit_price"] = _dec(lr[3])
        lines.append(line)
    return {
        "id": str(r[0]), "work_order_id": str(r[1]) if r[1] else None, "version": int(r[2]),
        "state": r[3], "total_amount": _dec(r[4]), "deposit_required": _dec(r[5]),
        "expiry_at": r[6].isoformat() if r[6] else None, "snapshot_hash": r[7],
        "is_mock": bool(r[8]), "lines": lines, "cost_visible": include_cost,
    }


async def transition(
    *, tenant_id: str, quote_id: str, action: str, actor_id: str | None = None,
    comment: str | None = None,
) -> dict:
    """狀態機轉換。send → 凍結 pricing snapshot；approve/reject → 記 quote_approval。"""
    if action not in _TRANSITIONS:
        raise ApiError("VALIDATION_ERROR", f"unknown action '{action}'", 422)
    conn = await _conn()
    from_states, to_state = _TRANSITIONS[action]
    cur = await (await conn.execute("SELECT state FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not cur:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if cur[0] not in from_states:
        raise ApiError("STATE_CONFLICT", f"cannot {action} quote in '{cur[0]}'", 409)

    # 核准門檻（esales Q-11，mock 預設）：總額超門檻不可從 draft 直送，須先 submit→approve
    if action == "send" and cur[0] == "draft":
        tot = await (await conn.execute(
            "SELECT COALESCE(total_amount, 0) FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if float(tot[0]) > _APPROVAL_THRESHOLD:
            raise ApiError(
                "APPROVAL_REQUIRED",
                f"報價總額超過 {_APPROVAL_THRESHOLD:.0f}（門檻待 esales Q-11 確認），須先送審核准",
                409,
            )

    # 過期檢查：sent 後逾 expiry 不可 accept
    if action == "accept":
        exp = await (await conn.execute("SELECT expiry_at FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if exp[0] and exp[0] < datetime.now(timezone.utc):
            await conn.execute("UPDATE quote SET state = 'expired', updated_at = NOW() WHERE id = %s::uuid", (quote_id,))
            raise ApiError("STATE_CONFLICT", "quote expired", 409)

    await conn.execute("UPDATE quote SET state = %s, updated_at = NOW() WHERE id = %s::uuid", (to_state, quote_id))

    if action in ("approve", "reject"):
        await conn.execute(
            "INSERT INTO quote_approval (quote_id, approver_id, decision, comment) "
            "VALUES (%s::uuid, %s::uuid, %s, %s)",
            (quote_id, actor_id, "approved" if action == "approve" else "rejected", comment))
    if action == "send":
        await _freeze_snapshot(quote_id, tenant_id)
    return await get_quote(quote_id=quote_id, tenant_id=tenant_id, include_cost=True)


async def _freeze_snapshot(quote_id: str, tenant_id: str) -> None:
    """送客戶當下凍結價格規則 + 算 hash（報價快照不可變）。"""
    conn = await _conn()
    lines = await (await conn.execute(
        "SELECT item_name, category, customer_price, quantity FROM quote_line_items "
        "WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    snap = {"lines": [{"name": l[0], "cat": l[1], "price": _dec(l[2]), "qty": int(l[3])} for l in lines]}
    blob = json.dumps(snap, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    await conn.execute(
        "INSERT INTO pricing_rule_snapshot (quote_id, rules_json, hash) VALUES (%s::uuid, %s::jsonb, %s)",
        (quote_id, blob, h))
    await conn.execute("UPDATE quote SET snapshot_hash = %s, updated_at = NOW() WHERE id = %s::uuid", (h, quote_id))
