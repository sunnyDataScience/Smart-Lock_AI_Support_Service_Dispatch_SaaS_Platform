"""Technician AP Statement Service — FR-0045 Phase II MVP。

師傅月結 statement：
  - generate_statement: 系統算當月完工 WO + 扣除 → INSERT draft
  - submit_for_review: draft → pending_review (送主管)
  - dispute_statement: pending_review → disputed (技師舉報異議)
  - approve_statement: pending_review → approved (主管核准)
  - reject_statement: pending_review → rejected (主管退回)
  - mark_paid: approved → paid (匯款)
  - get_statement: 技師 self-service 查詢

dispute window 預設 statement 送 review 後 7 天；超時自動 approved（cron 留下輪）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.technician_statement_service")

DISPUTE_WINDOW_DAYS = 7

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_review"},
    "pending_review": {"approved", "disputed", "rejected"},
    "disputed": {"pending_review", "rejected"},  # 主管處理後重 review
    "approved": {"paid"},
    "rejected": {"draft"},
    "paid": set(),  # 終態
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
    technician_id: str,
    period_year: int,
    period_month: int,
    gross_amount: float | None = None,
    travel_fee_deduction: float = 0.0,
    cash_collection_deduction: float = 0.0,
    dispute_hold_amount: float = 0.0,
    other_deductions: float = 0.0,
    total_completed_orders: int | None = None,
    notes: str | None = None,
) -> dict:
    """產 statement draft（月底 cron 自動跑或 admin manual 觸發）。

    冪等：同 tech + period 已存 → 回 existing。

    CR-0117 S4：gross_amount / total_completed_orders **省略（None）= 系統自動計算**
    —— 依 CR-0106 佣金口徑（固定工資制：完工單服務明細 × 該技師等級 base_payout，
    重用 compute_monthly_commission）。顯式帶值仍為人工覆寫（ops 修正用）。
    先前版本金額全靠手動參數（預設 0）、docstring 卻宣稱系統自算 —— 名實不符。
    扣項維持手動參數（結構化來源未建，CR-0106 既有誠實限制）。
    """
    if period_month < 1 or period_month > 12:
        raise ApiError("VALIDATION_ERROR", "period_month must be 1..12", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 冪等：UNIQUE constraint 阻 INSERT，先 SELECT（先於自動計算 —— 已存在就不必算佣金）
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.technician_statement "
        "WHERE tenant_id = %s::uuid AND technician_id = %s::uuid "
        "  AND period_year = %s AND period_month = %s",
        (tenant_id, technician_id, period_year, period_month),
    )
    existing = await cur.fetchone()
    if existing:
        logger.info(
            "statement idempotent hit: tech=%s %d-%02d",
            technician_id[:8], period_year, period_month,
        )
        return await _get(str(existing[0]))

    # 省略 gross → 依佣金口徑自動計算（顯式帶值 = 人工模式，維持既有語意含 count 預設 0）
    if gross_amount is None:
        from services import technician_commission_service

        commission = await technician_commission_service.compute_monthly_commission(
            tenant_id=tenant_id,
            technician_id=technician_id,
            year=period_year,
            month=period_month,
        )
        gross_amount = float(commission["gross_amount"])
        if total_completed_orders is None:
            total_completed_orders = int(commission["completed_orders"])
        if commission.get("unmapped_count"):
            # 有服務代碼對不到費率 → 記入 notes 供審核者辨識（不擋產生）
            warn = f"[自動計算] {commission['unmapped_count']} 項服務代碼未對到費率(以 0 計)"
            notes = f"{notes}；{warn}" if notes else warn
    if total_completed_orders is None:
        total_completed_orders = 0

    net = (
        float(gross_amount) - float(travel_fee_deduction)
        - float(cash_collection_deduction) - float(dispute_hold_amount)
        - float(other_deductions)
    )

    # CR-0117：ON CONFLICT DO NOTHING 補 TOCTOU 縫 —— 上方 SELECT 與此 INSERT 間若有
    # 並發 generate（cron tick 撞 ops 手動觸發），輸家不再 UNIQUE violation 500，
    # 改走冪等路徑回 existing。
    cur = await db_module._conn.execute(
        "INSERT INTO saas.technician_statement "
        "  (tenant_id, technician_id, period_year, period_month, "
        "   total_completed_orders, gross_amount, travel_fee_deduction, "
        "   cash_collection_deduction, dispute_hold_amount, other_deductions, "
        "   net_amount, notes) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tenant_id, technician_id, period_year, period_month) DO NOTHING "
        "RETURNING id",
        (
            tenant_id, technician_id, period_year, period_month,
            total_completed_orders,
            float(gross_amount), float(travel_fee_deduction),
            float(cash_collection_deduction), float(dispute_hold_amount),
            float(other_deductions), round(net, 2),
            notes,
        ),
    )
    row = await cur.fetchone()
    if row:
        return await _get(str(row[0]))
    # 並發輸家：撈贏家那筆回傳（與冪等 hit 同語意）
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.technician_statement "
        "WHERE tenant_id = %s::uuid AND technician_id = %s::uuid "
        "  AND period_year = %s AND period_month = %s",
        (tenant_id, technician_id, period_year, period_month),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("INTERNAL_ERROR", "statement insert race resolution failed", 500)
    return await _get(str(row[0]))


async def _assert_tenant(statement_id: str, tenant_id: str) -> None:
    """驗證 statement 屬於該租戶（2026-08-02 資安掃描）。

    原本 list 端點有租戶收斂，但 **detail 與全部狀態轉換（submit/dispute/approve/
    reject/mark_paid）完全不驗**——只要知道 statement UUID，任何租戶的管理者都能
    讀取他人的金額並核准、標記已付款。

    回 404 而非 403：403 會確認該 id 存在，可被用來列舉他租戶的對帳單。

    statement 的 tenant_id 不會變更，所以「驗證後才寫入」不存在 TOCTOU 問題。
    """
    cur = await db_module._conn.execute(
        "SELECT tenant_id FROM saas.technician_statement WHERE id = %s::uuid",
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
        "SELECT id, tenant_id, technician_id, period_year, period_month, "
        "       total_completed_orders, gross_amount, travel_fee_deduction, "
        "       cash_collection_deduction, dispute_hold_amount, "
        "       other_deductions, net_amount, status, dispute_window_ends_at, "
        "       disputed_at, dispute_reason, reviewed_by, reviewed_at, "
        "       paid_at, notes, created_at, updated_at "
        "FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "technician_id": str(row[2]),
        "period_year": row[3],
        "period_month": row[4],
        "total_completed_orders": row[5],
        "gross_amount": _dec(row[6]),
        "travel_fee_deduction": _dec(row[7]),
        "cash_collection_deduction": _dec(row[8]),
        "dispute_hold_amount": _dec(row[9]),
        "other_deductions": _dec(row[10]),
        "net_amount": _dec(row[11]),
        "status": row[12],
        "dispute_window_ends_at": row[13].isoformat() if row[13] else None,
        "disputed_at": row[14].isoformat() if row[14] else None,
        "dispute_reason": row[15],
        "reviewed_by": str(row[16]) if row[16] else None,
        "reviewed_at": row[17].isoformat() if row[17] else None,
        "paid_at": row[18].isoformat() if row[18] else None,
        "notes": row[19],
        "created_at": row[20].isoformat() if row[20] else None,
        "updated_at": row[21].isoformat() if row[21] else None,
    }


def _dec(v) -> str:
    if v is None:
        return "0.00"
    return f"{float(v):.2f}"


async def submit_for_review(*, statement_id: str, tenant_id: str) -> dict:
    """draft → pending_review；設 dispute_window_ends_at = NOW + 7 days。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "pending_review")

    window_ends = datetime.now(timezone.utc) + timedelta(days=DISPUTE_WINDOW_DAYS)
    await db_module._conn.execute(
        "UPDATE saas.technician_statement SET "
        "  status = 'pending_review', "
        "  dispute_window_ends_at = %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'draft'",
        (window_ends.isoformat(), statement_id),
    )
    return await _get(statement_id)


async def dispute_statement(
    *, statement_id: str, tenant_id: str, dispute_reason: str,
) -> dict:
    """技師舉報異議：pending_review → disputed。"""
    if not dispute_reason or len(dispute_reason.strip()) < 5:
        raise ApiError("VALIDATION_ERROR", "dispute_reason ≥5 字元", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT status, dispute_window_ends_at "
        "FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "disputed")
    # dispute window 過期 → 拒
    if row[1] and datetime.now(timezone.utc) > row[1].replace(tzinfo=timezone.utc):
        raise ApiError(
            "STATE_CONFLICT",
            "dispute window 已過期",
            409,
        )

    upd = await db_module._conn.execute(
        "UPDATE saas.technician_statement SET "
        "  status = 'disputed', "
        "  disputed_at = NOW(), "
        "  dispute_reason = %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' "
        "RETURNING id",
        (dispute_reason.strip()[:1000], statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def approve_statement(
    *, statement_id: str, tenant_id: str, reviewer_id: str,
) -> dict:
    """pending_review → approved (主管核准)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "approved")

    upd = await db_module._conn.execute(
        "UPDATE saas.technician_statement SET "
        "  status = 'approved', reviewed_by = %s::uuid, reviewed_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending_review' "
        "RETURNING id",
        (reviewer_id, statement_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return await _get(statement_id)


async def reject_statement(
    *, statement_id: str, tenant_id: str, reviewer_id: str, reason: str | None = None,
) -> dict:
    """pending_review|disputed → rejected (退回 draft 修)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "rejected")

    upd = await db_module._conn.execute(
        "UPDATE saas.technician_statement SET "
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
    """approved → paid (匯款執行)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    await _assert_tenant(statement_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.technician_statement WHERE id = %s::uuid",
        (statement_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "statement not found", 404)
    _check_transition(row[0], "paid")

    upd = await db_module._conn.execute(
        "UPDATE saas.technician_statement SET "
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
    technician_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if technician_id:
        where.append("technician_id = %s::uuid")
        args.append(technician_id)
    if status:
        where.append("status = %s")
        args.append(status)
    args.append(limit)

    cur = await db_module._conn.execute(
        "SELECT id FROM saas.technician_statement "
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
