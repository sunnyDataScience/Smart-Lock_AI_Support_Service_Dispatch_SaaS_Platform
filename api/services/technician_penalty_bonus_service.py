"""Technician Penalty/Bonus Service — CR-0107 師傅獎懲明細。

承載師傅詳情頁右欄「獎懲紀錄」真資料（取代前端寫死 4 筆 mock）。

**業主裁決（2026-06-27）「後台手動登錄 + 自動帶取消罰」**，因 ERP spec Q121 明令師傅扣款不可由
AI 自行假設 → 不腦補自動獎懲規則。兩來源合併：
  1. **手動登錄**：saas.technician_penalty_bonus_ledger（admin/主管逐筆登錄實際獎金/扣款，符合 Q121）。
  2. **自動帶入（read-only）**：public.cancellation.technician_penalty（取消失約扣款，BR-CANCEL-007
     規則明確；JOIN work_orders 取 technician_id）。

list 合併兩源依日期新→舊；create/delete 僅作用於手動 ledger（自動帶入不可編輯）。
"""

from __future__ import annotations

import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

_VALID_TYPES = {"bonus", "penalty"}


async def _assert_technician(tenant_id: str, technician_id: str) -> None:
    cur = await db_module._conn.execute(
        "SELECT 1 FROM technicians WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Technician not found", 404)


async def list_entries(*, tenant_id: str, technician_id: str) -> list[dict]:
    """合併手動 ledger + 自動帶入取消失約扣款，依日期新→舊。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    await _assert_technician(tenant_id, technician_id)

    entries: list[dict] = []

    # 1) 手動 ledger（可刪）
    cur = await db_module._conn.execute(
        "SELECT id, entry_type, title, reason, amount, occurred_date, source_work_order_id "
        "FROM saas.technician_penalty_bonus_ledger "
        "WHERE tenant_id = %s::uuid AND technician_id = %s::uuid",
        (tenant_id, technician_id),
    )
    for r in await cur.fetchall():
        entries.append({
            "id": str(r[0]),
            "entry_type": r[1],
            "title": r[2],
            "reason": r[3],
            "amount": float(r[4]),
            "occurred_date": r[5].isoformat() if r[5] else None,
            "source": "manual",
            "source_work_order_id": str(r[6]) if r[6] else None,
            "editable": True,
        })

    # 2) 自動帶入：取消失約扣款（read-only；JOIN work_orders 取技師、排除善意豁免）
    cur = await db_module._conn.execute(
        "SELECT c.id, c.technician_penalty, c.reason_code, c.created_at, c.work_order_id "
        "FROM cancellation c JOIN work_orders wo ON c.work_order_id = wo.id "
        "WHERE wo.technician_id = %s::uuid AND c.tenant_id = %s::uuid "
        "  AND c.technician_penalty IS NOT NULL AND c.technician_penalty > 0 "
        "  AND COALESCE(c.goodwill_waiver, FALSE) = FALSE",
        (technician_id, tenant_id),
    )
    for r in await cur.fetchall():
        reason_code = r[2] or ""
        entries.append({
            "id": f"cancel:{r[0]}",
            "entry_type": "penalty",
            "title": f"取消失約扣款{('（' + reason_code + '）') if reason_code else ''}",
            "reason": "工單取消累犯罰款（BR-CANCEL-007）",
            "amount": float(r[1]),
            "occurred_date": r[3].date().isoformat() if r[3] else None,
            "source": "cancellation",
            "source_work_order_id": str(r[4]) if r[4] else None,
            "editable": False,
        })

    # 依日期新→舊（None 日期排最後）
    entries.sort(key=lambda e: e["occurred_date"] or "", reverse=True)
    return entries


async def create_entry(
    *,
    tenant_id: str,
    technician_id: str,
    entry_type: str,
    title: str,
    amount: float,
    occurred_date: str,
    reason: str | None = None,
    source_work_order_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    """新增一筆手動獎懲（admin/主管登錄）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if entry_type not in _VALID_TYPES:
        raise ApiError("VALIDATION_ERROR", "entry_type 必須為 bonus 或 penalty", 422)
    if not title or not title.strip():
        raise ApiError("VALIDATION_ERROR", "title 必填", 422)
    if amount is None or float(amount) < 0:
        raise ApiError("VALIDATION_ERROR", "amount 必須 ≥ 0（正值；類型決定加減）", 422)
    if not occurred_date:
        raise ApiError("VALIDATION_ERROR", "occurred_date 必填", 422)
    await _assert_technician(tenant_id, technician_id)

    entry_id = str(uuid.uuid4())
    cur = await db_module._conn.execute(
        "INSERT INTO saas.technician_penalty_bonus_ledger "
        "  (id, tenant_id, technician_id, entry_type, title, reason, amount, "
        "   occurred_date, source_work_order_id, created_by) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::date, %s, %s) "
        "RETURNING id, entry_type, title, reason, amount, occurred_date, source_work_order_id",
        (
            entry_id, tenant_id, technician_id, entry_type, title.strip(),
            reason.strip() if reason else None, amount, occurred_date,
            source_work_order_id or None, created_by or None,
        ),
    )
    r = await cur.fetchone()
    return {
        "id": str(r[0]),
        "entry_type": r[1],
        "title": r[2],
        "reason": r[3],
        "amount": float(r[4]),
        "occurred_date": r[5].isoformat() if r[5] else None,
        "source": "manual",
        "source_work_order_id": str(r[6]) if r[6] else None,
        "editable": True,
    }


async def delete_entry(*, tenant_id: str, technician_id: str, entry_id: str) -> None:
    """刪除一筆手動獎懲（自動帶入的取消罰不可刪 —— id 帶 cancel: 前綴會擋下）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if entry_id.startswith("cancel:"):
        raise ApiError("VALIDATION_ERROR", "自動帶入的取消失約扣款不可刪除", 422)
    cur = await db_module._conn.execute(
        "DELETE FROM saas.technician_penalty_bonus_ledger "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND technician_id = %s::uuid "
        "RETURNING id",
        (entry_id, tenant_id, technician_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Entry not found", 404)
