"""Role 指派雙人 SoD service（CR-0071 / TI-RBAC-02 / FR-0019 / §4.6.5 SOD-ROLE-ASSIGN）。

使用者 role 變更走 propose → approve（不同人）→ apply 三段。SoD 核心：approver 不可
等於 proposer（service 層 403 SOD_VIOLATION_RBAC + DB 層 role_assign_dual_sign_distinct
CHECK 雙重防線）。階層強制重用 role_service.can_grant / RBAC_ADMIN_ROLES。

狀態機（照抄 reconciliation_exception 模式）：
  proposed → {approved, rejected, cancelled}
  approved → {applied, cancelled}
  applied / rejected / cancelled = 終態
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service
from services.role_service import (
    ALLOWED_TARGET_ROLES,
    RBAC_ADMIN_ROLES,
    can_grant,
)

logger = logging.getLogger("api.role_assignment_service")

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"approved", "rejected", "cancelled"},
    "approved": {"applied", "cancelled"},
    "applied": set(),
    "rejected": set(),
    "cancelled": set(),
}

_SELECT = (
    "id, tenant_id, target_user_id, from_role, to_role, status, "
    "proposed_by, proposed_at, approved_by, approved_at, reason"
)


def _check_transition(current: str, target: str) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ApiError("STATE_CONFLICT", f"cannot transition role assignment '{current}'→'{target}'", 409)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]), "tenant_id": str(row[1]), "target_user_id": str(row[2]),
        "from_role": row[3], "to_role": row[4], "status": row[5],
        "proposed_by": str(row[6]) if row[6] else None,
        "proposed_at": row[7].isoformat() if row[7] else None,
        "approved_by": str(row[8]) if row[8] else None,
        "approved_at": row[9].isoformat() if row[9] else None,
        "reason": row[10],
    }


async def propose_role_change(
    *, tenant_id: str, target_user_id: str, to_role: str,
    proposer_id: str, proposer_role: str, reason: str | None = None,
) -> dict:
    """step-1：建 status='proposed' 提案。

    驗證：proposer 須 RBAC_ADMIN_ROLES；to_role 合法；can_grant 階層強制；
    同 target 已有 open 提案（proposed/approved 未 apply）→ 409 防重複。
    """
    if proposer_role not in RBAC_ADMIN_ROLES:
        raise ApiError("FORBIDDEN", "proposer must be an RBAC admin role", 403)
    if to_role not in ALLOWED_TARGET_ROLES:
        raise ApiError("NOT_FOUND", f"unknown target role: {to_role}", 404)
    if not can_grant(proposer_role, to_role):
        raise ApiError("RBAC_HIERARCHY_VIOLATION",
                       f"role '{proposer_role}' cannot grant '{to_role}' (hierarchy)", 403)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 同 target 已有未結提案 → 409
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.role_assignment "
        "WHERE tenant_id=%s::uuid AND target_user_id=%s::uuid AND status IN ('proposed','approved') LIMIT 1",
        (tenant_id, target_user_id))
    if await cur.fetchone():
        raise ApiError("STATE_CONFLICT", "target user already has an open role-change proposal", 409)

    # 抓現有 role 寫 from_role
    fcur = await db_module._conn.execute(
        "SELECT role FROM users WHERE id=%s::uuid AND tenant_id=%s::uuid", (target_user_id, tenant_id))
    frow = await fcur.fetchone()
    if not frow:
        raise ApiError("NOT_FOUND", "target user not found", 404)
    from_role = frow[0]

    cur = await db_module._conn.execute(
        "INSERT INTO saas.role_assignment "
        "  (tenant_id, target_user_id, from_role, to_role, status, proposed_by, reason) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'proposed', %s::uuid, %s) "
        f"RETURNING {_SELECT}",
        (tenant_id, target_user_id, from_role, to_role, proposer_id, reason))
    row = await cur.fetchone()
    try:
        await audit_log_service.log_event(
            event_type="rbac", actor_id=proposer_id, actor_role=proposer_role,
            action="role.change_proposed", target_type="users", target_id=target_user_id,
            payload={"from_role": from_role, "to_role": to_role, "assignment_id": str(row[0])})
    except Exception as exc:  # noqa: BLE001
        logger.warning("role propose audit failed: %s", exc)
    return _row_to_dict(row)


async def approve_role_change(
    *, tenant_id: str, assignment_id: str, approver_id: str, approver_role: str,
) -> dict:
    """step-2：SoD 核心。approver ≠ proposer（403 SOD_VIOLATION_RBAC）；階層強制；樂觀鎖。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, proposed_by, to_role FROM saas.role_assignment "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid", (assignment_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "role assignment not found", 404)
    current, proposed_by, to_role = row[0], row[1], row[2]
    _check_transition(current, "approved")
    # SoD：approver 不可等於 proposer
    if proposed_by and str(proposed_by) == str(approver_id):
        raise ApiError("SOD_VIOLATION_RBAC", "approver must differ from proposer (SoD)", 403)
    if approver_role not in RBAC_ADMIN_ROLES:
        raise ApiError("FORBIDDEN", "approver must be an RBAC admin role", 403)
    if not can_grant(approver_role, to_role):
        raise ApiError("RBAC_HIERARCHY_VIOLATION",
                       f"role '{approver_role}' cannot approve grant of '{to_role}'", 403)
    upd = await db_module._conn.execute(
        "UPDATE saas.role_assignment SET status='approved', approved_by=%s::uuid, "
        "  approved_at=NOW(), updated_at=NOW() "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid AND status='proposed' "
        f"RETURNING {_SELECT}",
        (approver_id, assignment_id, tenant_id))
    out = await upd.fetchone()
    if not out:
        raise ApiError("STATE_CONFLICT", "concurrent state change (already decided)", 409)
    try:
        await audit_log_service.log_event(
            event_type="rbac", actor_id=approver_id, actor_role=approver_role,
            action="role.change_approved", target_type="users", target_id=str(out[2]),
            payload={"to_role": to_role, "assignment_id": assignment_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("role approve audit failed: %s", exc)
    return _row_to_dict(out)


async def apply_role_change(*, tenant_id: str, assignment_id: str) -> dict:
    """step-3：approved → applied。同 tx UPDATE users.role + 提案 applied（首個生產 role 指派路徑）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, target_user_id, to_role FROM saas.role_assignment "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid", (assignment_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "role assignment not found", 404)
    _check_transition(row[0], "applied")
    target_user_id, to_role = str(row[1]), row[2]
    # CR-0112 方案 B(雙庫模式):技師帳號屬身分權威庫,角色轉換會破壞
    # 技師域不變量(technician 列須同時存在 technicians 主檔)→ 擋下。
    # 單庫 fallback 行為不變。
    if db_module.tech_db_enabled():
        rcur = await db_module._conn.execute(
            "SELECT role FROM users WHERE id=%s::uuid", (target_user_id,))
        rrow = await rcur.fetchone()
        if (rrow and rrow[0] == "technician") or to_role == "technician":
            raise ApiError(
                "VALIDATION_ERROR",
                "技師帳號的角色不可經角色指派流程變更(技師身分庫拆分後之不變量)",
                422,
            )
    await db_module._conn.execute(
        "UPDATE users SET role=%s WHERE id=%s::uuid AND tenant_id=%s::uuid",
        (to_role, target_user_id, tenant_id))
    upd = await db_module._conn.execute(
        "UPDATE saas.role_assignment SET status='applied', updated_at=NOW() "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid AND status='approved' "
        f"RETURNING {_SELECT}", (assignment_id, tenant_id))
    out = await upd.fetchone()
    if not out:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    try:
        await audit_log_service.log_event(
            event_type="rbac", actor_id=None, actor_role="system",
            action="role.change_applied", target_type="users", target_id=target_user_id,
            payload={"to_role": to_role, "assignment_id": assignment_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("role apply audit failed: %s", exc)
    return _row_to_dict(out)


async def list_role_assignments(
    *, tenant_id: str, status: str | None = None, limit: int = 100,
) -> list[dict]:
    """審核佇列/歷史查詢（CR-0143 生產接線；預設全狀態、時間倒序）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    sql = f"SELECT {_SELECT} FROM saas.role_assignment WHERE tenant_id=%s::uuid"
    params: list = [tenant_id]
    if status:
        sql += " AND status=%s"
        params.append(status)
    sql += " ORDER BY proposed_at DESC LIMIT %s"
    params.append(limit)
    cur = await db_module._conn.execute(sql, params)
    return [_row_to_dict(r) for r in await cur.fetchall()]


async def reject_role_change(
    *, tenant_id: str, assignment_id: str, actor_id: str, actor_role: str,
    reason: str | None = None,
) -> dict:
    """proposed → rejected（留 audit；SoD 不限制拒絕者——擋壞提案不需雙人）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if actor_role not in RBAC_ADMIN_ROLES:
        raise ApiError("FORBIDDEN", "actor must be an RBAC admin role", 403)
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.role_assignment WHERE id=%s::uuid AND tenant_id=%s::uuid",
        (assignment_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "role assignment not found", 404)
    _check_transition(row[0], "rejected")
    upd = await db_module._conn.execute(
        "UPDATE saas.role_assignment SET status='rejected', "
        "  reason=COALESCE(%s, reason), updated_at=NOW() "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid AND status='proposed' "
        f"RETURNING {_SELECT}",
        (reason, assignment_id, tenant_id))
    out = await upd.fetchone()
    if not out:
        raise ApiError("STATE_CONFLICT", "concurrent state change (already decided)", 409)
    try:
        await audit_log_service.log_event(
            event_type="rbac", actor_id=actor_id, actor_role=actor_role,
            action="role.change_rejected", target_type="users", target_id=str(out[2]),
            payload={"assignment_id": assignment_id, "reason": reason})
    except Exception as exc:  # noqa: BLE001
        logger.warning("role reject audit failed: %s", exc)
    return _row_to_dict(out)
