"""CR-0041 M15 異常框架 service — exception_case lifecycle（BR-M15-01/03）。

control tower：缺料/改期/加價拒絕/取消/退款/爭議/安全風險統一追蹤。
- open：建異常；high/critical severity + 有 WO → 設 work_orders.high_risk_hold（BR-M15-03 暫停）。
- resolve：選 return_path（BR-M15-01 9 動作之一）；若該 WO 無其他 open high-risk 異常 → 解除 hold。
- return_path 只「記錄 + 提示」既有端點（cancel/refund/reassign 等已存在），本框架不重寫各動作（HD-1 MVP）。
"""

from __future__ import annotations

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

# 對齊 generated.py ExceptionType / Status / Severity + BR-M15-01 return_path
_EXCEPTION_TYPES = {
    "no_show", "customer_absent", "scope_change_rejected", "material_shortage",
    "delay_severe", "appearance_refused", "payment_failed", "quality_complaint",
    "schedule_conflict", "other",
}
_SEVERITIES = {"low", "medium", "high", "critical"}
_HIGH_RISK = {"high", "critical"}
_RETURN_PATHS = {
    "continue", "requote", "reschedule", "reassign", "new_wo",
    "cancel", "refund", "rma", "dispute",
}
_ACTIVE_STATUSES = ("open", "investigating", "escalated")

_SELECT = (
    "id, work_order_id, exception_type, status, severity, description, "
    "return_path, return_to_stage, triggers_circuit_breaker, resolution, "
    "resolved_at, created_at"
)


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


def _row_to_dict(r: tuple) -> dict:
    return {
        "id": str(r[0]),
        "work_order_id": str(r[1]) if r[1] else None,
        "exception_type": r[2],
        "status": r[3],
        "severity": r[4],
        "description": r[5],
        "return_path": r[6],
        "return_to_stage": r[7],
        "triggers_circuit_breaker": bool(r[8]),
        "resolution": r[9],
        "resolved_at": r[10].isoformat() if r[10] else None,
        "created_at": r[11].isoformat() if r[11] else None,
    }


async def open_exception(
    *,
    tenant_id: str,
    exception_type: str,
    work_order_id: str | None = None,
    severity: str = "medium",
    description: str | None = None,
    created_by: str | None = None,
) -> dict:
    """建異常。high/critical + 有 WO → 設 high_risk_hold（BR-M15-03）。"""
    if exception_type not in _EXCEPTION_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"exception_type must be one of {sorted(_EXCEPTION_TYPES)}",
            422,
        )
    if severity not in _SEVERITIES:
        raise ApiError("VALIDATION_ERROR", f"severity must be one of {sorted(_SEVERITIES)}", 422)
    conn = await _conn()
    cur = await conn.execute(
        "INSERT INTO saas.exception_case "
        "  (tenant_id, work_order_id, exception_type, severity, description, created_by) "
        "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
        f"RETURNING {_SELECT}",
        (tenant_id, work_order_id, exception_type, severity, description, created_by),
    )
    row = await cur.fetchone()
    if severity in _HIGH_RISK and work_order_id:
        await conn.execute(
            "UPDATE work_orders SET high_risk_hold = TRUE, updated_at = NOW() WHERE id = %s::uuid",
            (work_order_id,),
        )
    return _row_to_dict(row)


async def list_exceptions(
    *,
    tenant_id: str,
    status: str | None = None,
    severity: str | None = None,
    work_order_id: str | None = None,
    limit: int = 100,
) -> dict:
    conn = await _conn()
    sql = f"SELECT {_SELECT} FROM saas.exception_case WHERE tenant_id = %s::uuid "
    params: list = [tenant_id]
    if status:
        sql += "AND status = %s "
        params.append(status)
    if severity:
        sql += "AND severity = %s "
        params.append(severity)
    if work_order_id:
        sql += "AND work_order_id = %s::uuid "
        params.append(work_order_id)
    sql += "ORDER BY created_at DESC LIMIT %s"
    params.append(min(max(limit, 1), 500))
    cur = await conn.execute(sql, params)
    rows = await cur.fetchall()
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


async def get_exception(*, tenant_id: str, exception_id: str) -> dict:
    conn = await _conn()
    cur = await conn.execute(
        f"SELECT {_SELECT} FROM saas.exception_case "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (exception_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Exception not found", 404)
    return _row_to_dict(row)


async def resolve_exception(
    *,
    tenant_id: str,
    exception_id: str,
    return_path: str,
    resolution: str | None = None,
    return_to_stage: str | None = None,
    resolved_by: str | None = None,
) -> dict:
    """處理異常：選 return_path（BR-M15-01）→ status=resolved。

    return_path 為「決策記錄 + 指向既有端點」（HD-1）：實際 cancel/refund/reassign 仍由各既有端點執行。
    若該 WO 無其他 open high-risk 異常 → 解除 high_risk_hold。
    """
    if return_path not in _RETURN_PATHS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"return_path must be one of {sorted(_RETURN_PATHS)}",
            422,
        )
    conn = await _conn()
    cur = await conn.execute(
        "SELECT status, work_order_id FROM saas.exception_case "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid FOR UPDATE",
        (exception_id, tenant_id),
    )
    head = await cur.fetchone()
    if not head:
        raise ApiError("NOT_FOUND", "Exception not found", 404)
    if head[0] in ("resolved", "closed"):
        raise ApiError("STATE_CONFLICT", f"Exception already {head[0]}", 409)
    wo_id = head[1]

    cur2 = await conn.execute(
        "UPDATE saas.exception_case SET "
        "  status = 'resolved', return_path = %s, return_to_stage = %s, "
        "  resolution = %s, resolved_by = %s, resolved_at = NOW(), updated_at = NOW() "
        f"WHERE id = %s::uuid RETURNING {_SELECT}",
        (return_path, return_to_stage, resolution, resolved_by, exception_id),
    )
    row = await cur2.fetchone()

    # 解除 high_risk_hold（若該 WO 已無其他 open/escalated high-risk 異常）
    if wo_id:
        chk = await conn.execute(
            "SELECT 1 FROM saas.exception_case "
            "WHERE work_order_id = %s AND severity IN ('high', 'critical') "
            "  AND status IN ('open', 'investigating', 'escalated') LIMIT 1",
            (wo_id,),
        )
        if not await chk.fetchone():
            await conn.execute(
                "UPDATE work_orders SET high_risk_hold = FALSE, updated_at = NOW() WHERE id = %s",
                (wo_id,),
            )
    return _row_to_dict(row)


async def escalate_exception(*, tenant_id: str, exception_id: str) -> dict:
    conn = await _conn()
    cur = await conn.execute(
        "UPDATE saas.exception_case SET status = 'escalated', updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status NOT IN ('resolved', 'closed') "
        f"RETURNING {_SELECT}",
        (exception_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Exception not found or already closed", 404)
    return _row_to_dict(row)
