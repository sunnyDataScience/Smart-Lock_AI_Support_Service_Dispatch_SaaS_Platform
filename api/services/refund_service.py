"""Refund Requests 業務邏輯。

範圍：
- listRefundRequests（cursor + limit + status + work_order_id）
- getRefundRequest
- submitRefundDecision（pending → approved/rejected/escalated；append approval_chain）

OpenAPI RefundRequest schema：
    id, work_order_id, requested_by, amount (decimal str), reason, status (6 enum),
    created_at, updated_at; invoice_id?, complaint_id?, requires_dual_sign?,
    approval_chain (array of objects)?, executed_at?

DB ↔ API 對齊：
  - refund_requests.amount (FLOAT)        → decimal string with 2 decimals
  - refund_requests.status (varchar(50))  → API RefundRequestStatus，best-effort 直通：
        pending / approved / rejected / escalated / executed / cancelled
        非預期值 → 視為 pending（避免破壞 enum 約束）
  - approval_chain (jsonb)                → 直通；NULL → []
  - requires_dual_sign (bool)             → 直通；NULL → False

租戶隔離：refund_requests 沒 tenant_id，透過
    JOIN work_orders → problem_cards → conversations → users
延伸 4 層 JOIN 取 users.tenant_id 過濾（與 invoice_service 同 pattern）。

雙簽限制（MVP 簡化）：
  本 phase 不實作多步雙簽流程（DB 仍有 csm_approved/ops_approved/dual_signed 狀態，
  但 OpenAPI 沒對應 enum）。approve 一律單步推進到 'approved'，不再經 csm/ops 兩段。
  approval_chain 仍會 append 決策紀錄供稽核。後續若要拉雙簽，讀此檔對應 mapping。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.refund_service")


_VALID_API_STATUS = {
    "pending",
    "approved",
    "rejected",
    "escalated",
    "executed",
    "cancelled",
}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _coerce_status(raw: str | None) -> str:
    if raw and raw in _VALID_API_STATUS:
        return raw
    return "pending"


def _coerce_chain(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "invoice_id": str(row[2]) if row[2] else None,
        "complaint_id": str(row[3]) if row[3] else None,
        "requested_by": str(row[4]) if row[4] else None,
        "amount": _coerce_decimal(row[5]),
        "reason": row[6] or "",
        "status": _coerce_status(row[7]),
        "requires_dual_sign": bool(row[8]) if row[8] is not None else False,
        "approval_chain": _coerce_chain(row[9]),
        "executed_at": row[10].isoformat() if row[10] else None,
        "created_at": row[11].isoformat() if row[11] else None,
        "updated_at": row[12].isoformat() if row[12] else None,
    }


_SELECT = (
    "r.id, r.work_order_id, r.invoice_id, r.complaint_id, r.requested_by, "
    "r.amount, r.reason, r.status, r.requires_dual_sign, r.approval_chain, "
    "r.executed_at, r.created_at, r.updated_at"
)

_TENANT_JOIN = (
    "FROM refund_requests r "
    "JOIN work_orders wo ON r.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "JOIN conversations c ON pc.conversation_id = c.id "
    "JOIN users u ON c.user_id = u.id"
)


async def list_refund_requests(
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
        if status not in _VALID_API_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("r.status = %s")
        args.append(status)

    if work_order_id:
        where.append("r.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(r.created_at, r.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY r.created_at DESC, r.id DESC "
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
        next_cursor = encode_cursor({"ts": last[11].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_refund_request(*, tenant_id: str, refund_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE r.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (refund_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Refund request {refund_id} not found", 404)
    return _row_to_dict(row)


_DECISION_FROM = {"pending"}
_DECISION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "escalate": "escalated",
}


async def submit_decision(
    *,
    tenant_id: str,
    refund_id: str,
    decision: str,
    reason: str,
    decided_by_user_id: str,
) -> dict:
    """pending → approved / rejected / escalated；append approval_chain。"""
    if decision not in _DECISION_TO_STATUS:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be one of approve, reject, escalate",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT r.id, r.status, r.approval_chain "
        f"{_TENANT_JOIN} "
        f"WHERE r.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1",
        (refund_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Refund request {refund_id} not found", 404)
    current = row[1]
    if current not in _DECISION_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot decide refund in status '{current}'; expected 'pending'",
            409,
        )

    chain = _coerce_chain(row[2])
    chain.append(
        {
            "user_id": decided_by_user_id,
            "decision": decision,
            "reason": reason.strip()[:500],
            "decided_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    new_status = _DECISION_TO_STATUS[decision]
    await db_module._conn.execute(
        "UPDATE refund_requests "
        "SET status = %s, approval_chain = %s::jsonb, updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_status, json.dumps(chain), refund_id),
    )
    result = await get_refund_request(tenant_id=tenant_id, refund_id=refund_id)

    # 即時推送（best-effort）
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            "/realtime/refunds",
            {
                "type": "refund.decision.made",
                "payload": {
                    "refund_id": refund_id,
                    "decision": decision,
                    "status": new_status,
                    "decided_by_user_id": decided_by_user_id,
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish refund.decision failed (non-fatal)")

    return result
