"""CR-0027 公單成本拆項 service。

決議 4：後台看成本明細（含 unit_price 內部成本）、客戶端只露最終價。
決議 5：報價數字 mock（打 8 成）、is_mock=TRUE 待財務覆核。

RBAC 邊界（server 端遮蔽，非僅前端隱藏）：
  - include_cost=True（後台 admin/operations_manager）→ 回傳含 unit_price
  - include_cost=False（其他角色 / 客戶端）→ 不含 unit_price

對外總額：每次異動重算 work_orders.customer_final_amount = Σ(customer_price × quantity)。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.quote_service")

_VALID_CATEGORY = {"labor", "material", "other"}


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


def _row_to_item(row: tuple, *, include_cost: bool) -> dict:
    """row 對齊 _ITEM_SELECT。include_cost=False 時不輸出 unit_price。"""
    out = {
        "id": str(row[0]),
        "work_order_id": str(row[1]),
        "item_name": row[3],
        "category": row[4],
        "quantity": int(row[6]),
        "customer_price": _dec(row[7]),
        "is_mock": bool(row[8]),
    }
    if include_cost:
        out["unit_price"] = _dec(row[5])  # 內部成本 — 僅後台
    return out


_ITEM_SELECT = (
    "qli.id, qli.work_order_id, qli.tenant_id, qli.item_name, qli.category, "
    "qli.unit_price, qli.quantity, qli.customer_price, qli.is_mock"
)

# UAT P2-9：費用明細只計入「已同意」報價的品項——bind_quotes_to_work_order 會把
# PC 階段「所有版本」報價（含被拒/失效）的品項都回填 work_order_id，導致工單詳情
# 費用明細把 rejected 報價品項也算進來。可入帳範圍：
#   - qli.quote_id IS NULL：CR-0027 後台手動成本拆項（無報價單歸屬，維持入帳）
#   - quote.state = 'accepted'：客戶已確認報價
#   - quote.state = 'retrospective_audit_only'：急件補審佔位報價（實際施作品項）
_BILLABLE_ITEM_FILTER = (
    "(qli.quote_id IS NULL OR EXISTS ("
    "  SELECT 1 FROM quote q WHERE q.id = qli.quote_id "
    "    AND q.state IN ('accepted', 'retrospective_audit_only')))"
)


async def _recompute_final_amount(work_order_id: str) -> str | None:
    """重算 work_orders.customer_final_amount = Σ(customer_price × quantity)。

    UAT P2-9：只加總可入帳品項（_BILLABLE_ITEM_FILTER）——被拒報價的品項不入總計。
    """
    cur = await db_module._conn.execute(
        "SELECT COALESCE(SUM(qli.customer_price * qli.quantity), 0) "
        "FROM quote_line_items qli "
        f"WHERE qli.work_order_id = %s::uuid AND {_BILLABLE_ITEM_FILTER}",
        (work_order_id,),
    )
    total = (await cur.fetchone())[0]
    await db_module._conn.execute(
        "UPDATE work_orders SET customer_final_amount = %s, updated_at = NOW() "
        "WHERE id = %s::uuid",
        (total, work_order_id),
    )
    return _dec(total)


async def list_line_items(
    *, tenant_id: str, work_order_id: str, include_cost: bool
) -> dict:
    """列出公單成本拆項 + 對外總額。include_cost 決定是否含 unit_price（RBAC）。

    UAT P2-9：只列可入帳品項（_BILLABLE_ITEM_FILTER，被拒報價品項不混入）；
    總計以可入帳品項現算（列表與總計永遠一致，且不回 null——歷史單
    customer_final_amount 從未重算時原本會回 null）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # tenant 隔離：work_order 須屬該 tenant（走 users join，與 _WO_JOIN 一致）
    await _assert_wo_in_tenant(work_order_id, tenant_id)
    cur = await db_module._conn.execute(
        f"SELECT {_ITEM_SELECT} FROM quote_line_items qli "
        f"WHERE qli.work_order_id = %s::uuid AND {_BILLABLE_ITEM_FILTER} "
        "ORDER BY qli.created_at ASC",
        (work_order_id,),
    )
    rows = await cur.fetchall()
    items = [_row_to_item(r, include_cost=include_cost) for r in rows]
    final_amount = _dec(sum(
        float(i["customer_price"] or 0) * i["quantity"] for i in items
    ))
    return {
        "items": items,
        "customer_final_amount": final_amount,
        "cost_visible": include_cost,
    }


async def add_line_item(
    *,
    tenant_id: str,
    work_order_id: str,
    item_name: str,
    category: str,
    unit_price,
    quantity: int,
    customer_price,
    is_mock: bool = True,
) -> dict:
    """新增一筆成本拆項並重算對外總額。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if category not in _VALID_CATEGORY:
        raise ApiError(
            "VALIDATION_ERROR",
            f"category must be one of {sorted(_VALID_CATEGORY)}",
            422,
        )
    await _assert_wo_in_tenant(work_order_id, tenant_id)
    cur = await db_module._conn.execute(
        "INSERT INTO quote_line_items "
        "  (work_order_id, tenant_id, item_name, category, unit_price, quantity, "
        "   customer_price, is_mock) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) RETURNING id",
        (work_order_id, tenant_id, item_name, category, unit_price, quantity,
         customer_price, is_mock),
    )
    new_id = str((await cur.fetchone())[0])
    final_amount = await _recompute_final_amount(work_order_id)
    return {"id": new_id, "work_order_id": work_order_id,
            "customer_final_amount": final_amount}


async def _assert_wo_in_tenant(work_order_id: str, tenant_id: str) -> None:
    """work_order 必須屬該 tenant（走 wo.tenant_id 或 users join 回退）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (work_order_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Work order not found in this tenant", 404)
