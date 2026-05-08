"""Scope Change 業務邏輯（Q9=B 公開回覆機制）。

對應 SQL/Schema.sql 中的 ``scope_changes`` 表。本服務負責：

1. ``get_proposal_public(proposal_id)``: 公開取得提案（消費者匿名頁面）
   - 不做 tenant gate（呼叫者必須先驗 token 才能進來）
   - 回傳遮罩後可外露的欄位
   - 過期 / 已決議 / 不存在 → ``None`` 或 ``ApiError``

2. ``respond_public(proposal_id, decision, ...)``: 寫入消費者決定
   - decision ∈ {"accept", "reject"}
   - 同步更新 ``scope_changes.status`` + ``customer_decision``
   - decision="accept" → work_orders.status 升級為 in_progress
   - decision="reject" → 標記為 customer_rejected（後續由技師重新評估）
   - 寫 audit log（best-effort，失敗不影響主流程）
   - 重複決議 → 409 Conflict
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service

logger = logging.getLogger("api.scope_change_service")

Decision = Literal["accept", "reject"]

# scope_changes.status 對應消費者狀態
_PUBLIC_STATUS_MAP: dict[str, str] = {
    "pending": "pending",
    "customer_approved": "accepted",
    "customer_rejected": "rejected",
    "admin_override": "accepted",  # 管理員覆寫視為已決議
}


def _scope_to_items(scope_json: Any) -> list[dict]:
    """new_scope JSONB → 對外 items 陣列。

    new_scope 可能是 dict（單一變更）或 list（多個項目）。
    """
    if not scope_json:
        return []
    if isinstance(scope_json, str):
        try:
            scope_json = json.loads(scope_json)
        except json.JSONDecodeError:
            return []
    if isinstance(scope_json, list):
        return [_normalize_item(item) for item in scope_json if item]
    if isinstance(scope_json, dict):
        items = scope_json.get("items")
        if isinstance(items, list):
            return [_normalize_item(item) for item in items if item]
        return [_normalize_item(scope_json)]
    return []


def _normalize_item(item: Any) -> dict:
    if not isinstance(item, dict):
        return {"name": str(item), "description": None, "quantity": 1, "amount_delta": 0.0}
    return {
        "name": str(item.get("name") or item.get("title") or "變更項目"),
        "description": item.get("description") or item.get("desc"),
        "quantity": int(item.get("quantity") or 1),
        "amount_delta": float(item.get("amount_delta") or item.get("price_delta") or 0.0),
    }


async def get_proposal_public(*, proposal_id: str) -> dict | None:
    """讀取 scope_change 提案對外可揭露欄位。

    Returns:
        dict 含 proposal_id / work_order_id / status / reason / items /
        total_delta / expires_at；查無 → None。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        "SELECT id, work_order_id, status, reason, original_scope, new_scope, "
        "       original_price, new_price, customer_decision, created_at, updated_at "
        "FROM scope_changes "
        "WHERE id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (proposal_id,))
    row = await cur.fetchone()
    if not row:
        return None

    raw_status = row[2] or "pending"
    items = _scope_to_items(row[5])
    original_price = float(row[6] or 0.0)
    new_price = float(row[7]) if row[7] is not None else None
    total_delta = (new_price - original_price) if new_price is not None else sum(
        item["amount_delta"] for item in items
    )

    return {
        "proposal_id": str(row[0]),
        "work_order_id": str(row[1]),
        "status": _PUBLIC_STATUS_MAP.get(raw_status, raw_status),
        "raw_status": raw_status,
        "reason": row[3],
        "items": items,
        "total_delta": round(total_delta, 2),
        "original_price": original_price,
        "new_price": new_price,
        "customer_decision": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


async def respond_public(
    *,
    proposal_id: str,
    decision: Decision,
    comment: str | None = None,
    token_hash: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """記錄消費者對 scope_change 提案的回覆。

    Raises:
        ApiError(404): proposal 不存在
        ApiError(409): proposal 已決議（重複呼叫）
        ApiError(503): DB 不可用

    Returns:
        dict 含 proposal_id / decision / recorded_at / next_step
    """
    if decision not in ("accept", "reject"):
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 取目前提案 + 鎖定條件（autocommit 模式下無 row lock，採 status 條件 update）
    cur = await db_module._conn.execute(
        "SELECT status, work_order_id FROM scope_changes WHERE id = %s::uuid",
        (proposal_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "scope change proposal not found", 404)

    current_status, work_order_id = row[0], row[1]
    if current_status not in ("pending",):
        raise ApiError(
            "CONFLICT",
            f"proposal already decided: {current_status}",
            409,
        )

    # 2. 條件式 update（CAS：只有 status=pending 才寫入）
    new_status = "customer_approved" if decision == "accept" else "customer_rejected"
    customer_decision = "continue" if decision == "accept" else "cancel"
    upd = await db_module._conn.execute(
        "UPDATE scope_changes "
        "SET status = %s, customer_decision = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending' "
        "RETURNING id",
        (new_status, customer_decision, proposal_id),
    )
    updated_row = await upd.fetchone()
    if not updated_row:
        # race：另一個請求搶先決議
        raise ApiError("CONFLICT", "proposal already decided (race)", 409)

    # 3. 連動 work_orders（accept → in_progress；reject → 不動，由後台重派）
    if decision == "accept":
        try:
            await db_module._conn.execute(
                "UPDATE work_orders SET status = 'in_progress', updated_at = NOW() "
                "WHERE id = %s::uuid AND status IN ('accepted', 'in_progress')",
                (str(work_order_id),),
            )
        except Exception as exc:  # noqa: BLE001 — 主流程已寫入，連動失敗 audit
            logger.warning("scope_change accept work_order update failed: %s", exc)

    # 4. Audit log（best-effort）
    try:
        await audit_log_service.log_event(
            event_type="scope_change",
            actor_id=None,
            actor_role="public_consumer",
            action=f"scope_change_{decision}",
            target_type="scope_changes",
            target_id=proposal_id,
            payload={
                "decision": decision,
                "comment": comment,
                "token_hash": token_hash,
                "work_order_id": str(work_order_id),
            },
            ip_address=ip_address,
        )
    except Exception as exc:  # noqa: BLE001 — 不影響主流程
        logger.warning("scope_change audit log failed: %s", exc)

    next_step = (
        "技師將於 5 分鐘內收到通知並繼續施工。"
        if decision == "accept"
        else "我們已通知技師，後續將由客服重新評估後與您聯絡。"
    )

    return {
        "proposal_id": proposal_id,
        "decision": decision,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "next_step": next_step,
    }
