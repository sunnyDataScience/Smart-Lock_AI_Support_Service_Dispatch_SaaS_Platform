"""Brand B2B Settlement Service — FR-0047 Phase II MVP（Phase II 第 9 個收尾）。

品牌 B2B 月結：AR (品牌付服務費) + AP (平台付 commission) 雙向，NET direction
同月相沖；同 FR-0045/0046 6 狀態機 pattern + dispute window 7d。

Net 計算規則（direction='NET' 時）：
  net_amount = ar_service_fee - ap_commission + warranty_deduction + sla_penalty
  net_payable_to = 'brand' if net_amount < 0 else 'platform'
    (net_amount < 0 表示 platform 欠 brand；> 0 表示 brand 欠 platform)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.brand_b2b_statement_service")

DISPUTE_WINDOW_DAYS = 7

_VALID_DIRECTIONS = {"AR", "AP", "NET"}

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


def _compute_net(
    *,
    direction: str,
    ar_service_fee: float,
    ap_commission: float,
    warranty_deduction: float,
    sla_penalty: float,
) -> tuple[float, str | None]:
    """回傳 (net_amount, net_payable_to)。

    direction=='NET':
      net = ar - ap + warranty_deduction + sla_penalty
      > 0 → brand 欠 platform (net_payable_to='platform')
      < 0 → platform 欠 brand (net_payable_to='brand')
      == 0 → None
    direction=='AR': net = ar_service_fee (brand 應付平台)
    direction=='AP': net = ap_commission - warranty_deduction - sla_penalty (平台應付 brand)
    """
    if direction == "AR":
        return round(float(ar_service_fee), 2), "platform"
    if direction == "AP":
        net = round(
            float(ap_commission) - float(warranty_deduction) - float(sla_penalty),
            2,
        )
        return net, "brand"
    # NET
    net = round(
        float(ar_service_fee) - float(ap_commission)
        + float(warranty_deduction) + float(sla_penalty),
        2,
    )
    if net > 0:
        return net, "platform"  # brand 欠 platform
    if net < 0:
        return net, "brand"     # platform 欠 brand
    return 0.0, None


async def generate_statement(
    *,
    tenant_id: str,
    brand_partner_id: str,
    brand_name: str,
    period_year: int,
    period_month: int,
    direction: str = "NET",
    contract_ref: str | None = None,
    total_service_orders: int = 0,
    total_warranty_claims: int = 0,
    sla_breach_count: int = 0,
    ar_service_fee: float = 0.0,
    ap_commission: float = 0.0,
    warranty_deduction: float = 0.0,
    sla_penalty: float = 0.0,
    notes: str | None = None,
) -> dict:
    if period_month < 1 or period_month > 12:
        raise ApiError("VALIDATION_ERROR", "period_month must be 1..12", 422)
    if direction not in _VALID_DIRECTIONS:
        raise ApiError(
            "VALIDATION_ERROR", f"invalid direction: {direction}", 422,
        )
    if not brand_name or len(brand_name.strip()) < 1:
        raise ApiError("VALIDATION_ERROR", "brand_name required", 422)
    for n, v in (
        ("total_service_orders", total_service_orders),
        ("total_warranty_claims", total_warranty_claims),
        ("sla_breach_count", sla_breach_count),
    ):
        if v < 0:
            raise ApiError("VALIDATION_ERROR", f"{n} must be >= 0", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    net_amount, net_payable_to = _compute_net(
        direction=direction,
        ar_service_fee=ar_service_fee,
        ap_commission=ap_commission,
        warranty_deduction=warranty_deduction,
        sla_penalty=sla_penalty,
    )

    # 冪等
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.brand_b2b_statement "
        "WHERE tenant_id = %s::uuid AND brand_partner_id = %s::uuid "
        "  AND period_year = %s AND period_month = %s AND direction = %s",
        (tenant_id, brand_partner_id, period_year, period_month, direction),
    )
    existing = await cur.fetchone()
    if existing:
        return await _get(str(existing[0]))

    cur = await db_module._conn.execute(
        "INSERT INTO saas.brand_b2b_statement "
        "  (tenant_id, brand_partner_id, brand_name, contract_ref, "
        "   period_year, period_month, direction, "
        "   total_service_orders, total_warranty_claims, sla_breach_count, "
        "   ar_service_fee, ap_commission, warranty_deduction, sla_penalty, "
        "   net_amount, net_payable_to, notes) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, "
        "        %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id",
        (
            tenant_id, brand_partner_id, brand_name.strip()[:200],
            contract_ref, period_year, period_month, direction,
            total_service_orders, total_warranty_claims, sla_breach_count,
            float(ar_service_fee), float(ap_commission),
            float(warranty_deduction), float(sla_penalty),
            net_amount, net_payable_to, notes,
        ),
    )
    row = await cur.fetchone()
    return await _get(str(row[0]))


def _dec(v) -> str:
    if v is None:
        return "0.00"
    return f"{float(v):.2f}"


async def _get(statement_id: str) -> dict:
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, brand_partner_id, brand_name, contract_ref, "
        "       period_year, period_month, direction, "
        "       total_service_orders, total_warranty_claims, sla_breach_count, "
        "       ar_service_fee, ap_commission, warranty_deduction, sla_penalty, "
        "       net_amount, net_payable_to, status, dispute_window_ends_at, "
        "       disputed_at, dispute_reason, reviewed_by, reviewed_at, paid_at, "
        "       notes, created_at, updated_at "
        "FROM saas.brand_b2b_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "brand_partner_id": str(row[2]),
        "brand_name": row[3],
        "contract_ref": row[4],
        "period_year": row[5],
        "period_month": row[6],
        "direction": row[7],
        "total_service_orders": row[8],
        "total_warranty_claims": row[9],
        "sla_breach_count": row[10],
        "ar_service_fee": _dec(row[11]),
        "ap_commission": _dec(row[12]),
        "warranty_deduction": _dec(row[13]),
        "sla_penalty": _dec(row[14]),
        "net_amount": _dec(row[15]),
        "net_payable_to": row[16],
        "status": row[17],
        "dispute_window_ends_at": row[18].isoformat() if row[18] else None,
        "disputed_at": row[19].isoformat() if row[19] else None,
        "dispute_reason": row[20],
        "reviewed_by": str(row[21]) if row[21] else None,
        "reviewed_at": row[22].isoformat() if row[22] else None,
        "paid_at": row[23].isoformat() if row[23] else None,
        "notes": row[24],
        "created_at": row[25].isoformat() if row[25] else None,
        "updated_at": row[26].isoformat() if row[26] else None,
    }


# ---- 狀態機 ops (鏡像 FR-0045/0046) ----

async def submit_for_review(*, statement_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.brand_b2b_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "pending_review")
    window_ends = datetime.now(timezone.utc) + timedelta(days=DISPUTE_WINDOW_DAYS)
    await db_module._conn.execute(
        "UPDATE saas.brand_b2b_statement SET "
        "  status = 'pending_review', dispute_window_ends_at = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'draft'",
        (window_ends.isoformat(), statement_id),
    )
    return await _get(statement_id)


async def dispute_statement(
    *, statement_id: str, dispute_reason: str,
) -> dict:
    if not dispute_reason or len(dispute_reason.strip()) < 5:
        raise ApiError("VALIDATION_ERROR", "dispute_reason ≥5 字元", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, dispute_window_ends_at FROM saas.brand_b2b_statement "
        "WHERE id = %s::uuid", (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "disputed")
    if row[1] and datetime.now(timezone.utc) > row[1].replace(tzinfo=timezone.utc):
        raise ApiError("STATE_CONFLICT", "dispute window 已過期", 409)
    upd = await db_module._conn.execute(
        "UPDATE saas.brand_b2b_statement SET "
        "  status = 'disputed', disputed_at = NOW(), "
        "  dispute_reason = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' RETURNING id",
        (dispute_reason.strip()[:1000], statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def approve_statement(*, statement_id: str, reviewer_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.brand_b2b_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "approved")
    upd = await db_module._conn.execute(
        "UPDATE saas.brand_b2b_statement SET "
        "  status = 'approved', reviewed_by = %s::uuid, reviewed_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' RETURNING id",
        (reviewer_id, statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def reject_statement(
    *, statement_id: str, reviewer_id: str, reason: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.brand_b2b_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "rejected")
    upd = await db_module._conn.execute(
        "UPDATE saas.brand_b2b_statement SET "
        "  status = 'rejected', reviewed_by = %s::uuid, reviewed_at = NOW(), "
        "  notes = COALESCE(%s, notes), updated_at = NOW() "
        "WHERE id = %s::uuid AND status IN ('pending_review', 'disputed') "
        "RETURNING id",
        (reviewer_id, reason, statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def mark_paid(*, statement_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.brand_b2b_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "paid")
    upd = await db_module._conn.execute(
        "UPDATE saas.brand_b2b_statement SET "
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
    brand_partner_id: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)
    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if brand_partner_id:
        where.append("brand_partner_id = %s::uuid")
        args.append(brand_partner_id)
    if direction:
        if direction not in _VALID_DIRECTIONS:
            raise ApiError(
                "VALIDATION_ERROR", f"invalid direction: {direction}", 422,
            )
        where.append("direction = %s")
        args.append(direction)
    if status:
        where.append("status = %s")
        args.append(status)
    args.append(limit)
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.brand_b2b_statement "
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
