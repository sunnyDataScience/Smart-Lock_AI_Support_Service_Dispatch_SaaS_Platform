"""Dispatcher Commission Statement Service — FR-0046 Phase II MVP。

派工人月結 commission：結構同 FR-0045 (狀態機 + dispute window) 但對象為
dispatcher_user_id；金額拆解為 base_commission + performance_bonus - penalty。

7 ops（與 FR-0045 同 pattern）：
  generate / submit_for_review / dispute / approve / reject / mark_paid / list
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.dispatcher_commission_service")

DISPUTE_WINDOW_DAYS = 7

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_review"},
    "pending_review": {"approved", "disputed", "rejected"},
    "disputed": {"pending_review", "rejected"},
    "approved": {"paid"},
    "rejected": {"draft"},
    "paid": set(),
}


def _check_transition(current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot transition from '{current}' to '{target}'",
            409,
        )


async def generate_statement(
    *,
    tenant_id: str,
    dispatcher_user_id: str,
    period_year: int,
    period_month: int,
    total_dispatched_orders: int = 0,
    total_completed_orders: int = 0,
    avg_customer_satisfaction: float | None = None,
    base_commission: float = 0.0,
    performance_bonus: float = 0.0,
    penalty: float = 0.0,
    notes: str | None = None,
) -> dict:
    if period_month < 1 or period_month > 12:
        raise ApiError("VALIDATION_ERROR", "period_month must be 1..12", 422)
    if total_dispatched_orders < 0 or total_completed_orders < 0:
        raise ApiError("VALIDATION_ERROR", "orders count must >= 0", 422)
    if total_completed_orders > total_dispatched_orders:
        raise ApiError(
            "VALIDATION_ERROR",
            "completed_orders cannot exceed dispatched_orders",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    completion_rate_pct = (
        round(100.0 * total_completed_orders / total_dispatched_orders, 2)
        if total_dispatched_orders > 0 else 0.0
    )
    net = round(float(base_commission) + float(performance_bonus) - float(penalty), 2)

    # 冪等
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.dispatcher_commission_statement "
        "WHERE tenant_id = %s::uuid AND dispatcher_user_id = %s::uuid "
        "  AND period_year = %s AND period_month = %s",
        (tenant_id, dispatcher_user_id, period_year, period_month),
    )
    existing = await cur.fetchone()
    if existing:
        return await _get(str(existing[0]))

    cur = await db_module._conn.execute(
        "INSERT INTO saas.dispatcher_commission_statement "
        "  (tenant_id, dispatcher_user_id, period_year, period_month, "
        "   total_dispatched_orders, total_completed_orders, "
        "   completion_rate_pct, avg_customer_satisfaction, "
        "   base_commission, performance_bonus, penalty, net_commission, "
        "   notes) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id",
        (
            tenant_id, dispatcher_user_id, period_year, period_month,
            total_dispatched_orders, total_completed_orders,
            completion_rate_pct, avg_customer_satisfaction,
            float(base_commission), float(performance_bonus),
            float(penalty), net, notes,
        ),
    )
    row = await cur.fetchone()
    return await _get(str(row[0]))


def _dec(v) -> str:
    if v is None:
        return "0.00"
    return f"{float(v):.2f}"


async def _assert_tenant(statement_id: str, tenant_id: str) -> None:
    """驗證 statement 屬於該租戶（2026-08-02 資安掃描）。

    list 端點有租戶收斂，但 detail 與全部狀態轉換沒有——知道 UUID 就能讀他人金額
    並核准／標記已付款。回 404 而非 403（403 會確認存在性，可被列舉）。
    statement 的 tenant_id 不會變更，故驗證後才寫入不存在 TOCTOU。
    """
    cur = await db_module._conn.execute(
        "SELECT tenant_id FROM saas.dispatcher_commission_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    if str(row[0]) != str(tenant_id):
        logger.warning(
            "cross-tenant statement access blocked stmt=%s owner=%s caller=%s",
            statement_id, row[0], tenant_id,
        )
        raise ApiError("NOT_FOUND", "statement not found", 404)


async def _get(statement_id: str) -> dict:
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, dispatcher_user_id, period_year, period_month, "
        "       total_dispatched_orders, total_completed_orders, "
        "       completion_rate_pct, avg_customer_satisfaction, "
        "       base_commission, performance_bonus, penalty, net_commission, "
        "       status, dispute_window_ends_at, disputed_at, dispute_reason, "
        "       reviewed_by, reviewed_at, paid_at, notes, created_at, updated_at "
        "FROM saas.dispatcher_commission_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "dispatcher_user_id": str(row[2]),
        "period_year": row[3],
        "period_month": row[4],
        "total_dispatched_orders": row[5],
        "total_completed_orders": row[6],
        "completion_rate_pct": _dec(row[7]),
        "avg_customer_satisfaction": (
            float(row[8]) if row[8] is not None else None
        ),
        "base_commission": _dec(row[9]),
        "performance_bonus": _dec(row[10]),
        "penalty": _dec(row[11]),
        "net_commission": _dec(row[12]),
        "status": row[13],
        "dispute_window_ends_at": row[14].isoformat() if row[14] else None,
        "disputed_at": row[15].isoformat() if row[15] else None,
        "dispute_reason": row[16],
        "reviewed_by": str(row[17]) if row[17] else None,
        "reviewed_at": row[18].isoformat() if row[18] else None,
        "paid_at": row[19].isoformat() if row[19] else None,
        "notes": row[20],
        "created_at": row[21].isoformat() if row[21] else None,
        "updated_at": row[22].isoformat() if row[22] else None,
    }


async def submit_for_review(*, statement_id: str, tenant_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispatcher_commission_statement "
        "WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "pending_review")
    window_ends = datetime.now(timezone.utc) + timedelta(days=DISPUTE_WINDOW_DAYS)
    await db_module._conn.execute(
        "UPDATE saas.dispatcher_commission_statement SET "
        "  status = 'pending_review', "
        "  dispute_window_ends_at = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'draft'",
        (window_ends.isoformat(), statement_id),
    )
    return await _get(statement_id)


async def dispute_statement(
    *, statement_id: str, tenant_id: str, dispute_reason: str,
) -> dict:
    if not dispute_reason or len(dispute_reason.strip()) < 5:
        raise ApiError("VALIDATION_ERROR", "dispute_reason ≥5 字元", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)
    cur = await db_module._conn.execute(
        "SELECT status, dispute_window_ends_at FROM saas.dispatcher_commission_statement "
        "WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "disputed")
    if row[1] and datetime.now(timezone.utc) > row[1].replace(tzinfo=timezone.utc):
        raise ApiError("STATE_CONFLICT", "dispute window 已過期", 409)
    upd = await db_module._conn.execute(
        "UPDATE saas.dispatcher_commission_statement SET "
        "  status = 'disputed', disputed_at = NOW(), "
        "  dispute_reason = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' RETURNING id",
        (dispute_reason.strip()[:1000], statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def approve_statement(*, statement_id: str, tenant_id: str, reviewer_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispatcher_commission_statement "
        "WHERE id = %s::uuid", (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "approved")
    upd = await db_module._conn.execute(
        "UPDATE saas.dispatcher_commission_statement SET "
        "  status = 'approved', reviewed_by = %s::uuid, reviewed_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' RETURNING id",
        (reviewer_id, statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def reject_statement(
    *, statement_id: str, tenant_id: str, reviewer_id: str, reason: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispatcher_commission_statement "
        "WHERE id = %s::uuid", (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "rejected")
    upd = await db_module._conn.execute(
        "UPDATE saas.dispatcher_commission_statement SET "
        "  status = 'rejected', reviewed_by = %s::uuid, reviewed_at = NOW(), "
        "  notes = COALESCE(%s, notes), updated_at = NOW() "
        "WHERE id = %s::uuid AND status IN ('pending_review', 'disputed') "
        "RETURNING id",
        (reviewer_id, reason, statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def mark_paid(*, statement_id: str, tenant_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispatcher_commission_statement "
        "WHERE id = %s::uuid", (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "paid")
    upd = await db_module._conn.execute(
        "UPDATE saas.dispatcher_commission_statement SET "
        "  status = 'paid', paid_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'approved' RETURNING id",
        (statement_id,),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def list_statements(
    *,
    tenant_id: str,
    dispatcher_user_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)
    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if dispatcher_user_id:
        where.append("dispatcher_user_id = %s::uuid")
        args.append(dispatcher_user_id)
    if status:
        where.append("status = %s")
        args.append(status)
    args.append(limit)
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.dispatcher_commission_statement "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY period_year DESC, period_month DESC, created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = []
    for r in rows:
        try:
            items.append(await _get(str(r[0])))
        except ApiError:
            continue
    return {"items": items, "total": len(items)}
