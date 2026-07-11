"""Technician Lifecycle Service — FR-0044 Phase II MVP。

師傅完整生命週期管理：onboarding → active ↔ suspended → terminated。

提供 5 操作：
  - approve_onboarding(tech_id, actor): pending_approval → active
  - reject_onboarding(tech_id, actor, reason): pending_approval → rejected
  - suspend(tech_id, actor, reason): active → suspended
  - reactivate(tech_id, actor, reason): suspended → active
  - terminate(tech_id, actor, reason): 任何 → terminated（終態）

每次狀態變動寫 saas.technician_lifecycle_event audit row 含 actor + 原因。

狀態機允許轉移：
  pending_approval → active (approve) | rejected (reject)
  active → suspended (suspend) | terminated
  suspended → active (reactivate) | terminated
  rejected → terminated（rejected 為「未上線」非終態，可重新申請）
  terminated 為終態，不可再變
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.tech_mirror import mirror_rows

# CR-0112 方案 B:生命週期屬技師身分域 —— technicians/users 寫入落權威庫
# (require_tech_conn,單庫 fallback 時即主連線),完成後鏡射投影;
# saas.technician_lifecycle_event 單一居所在技師庫(讀寫都在那)。

logger = logging.getLogger("api.technician_lifecycle_service")


# 狀態機允許轉移
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending_approval": {"active", "rejected"},
    "active": {"suspended", "terminated"},
    "suspended": {"active", "terminated"},
    "rejected": {"terminated"},
    "terminated": set(),  # 終態
    "inactive": {"active", "terminated"},  # 既有狀態
}

# event_type ↔ (from, to) 對應
_EVENT_TRANSITIONS: dict[str, tuple[str, str]] = {
    "onboarding_approved": ("pending_approval", "active"),
    "onboarding_rejected": ("pending_approval", "rejected"),
    "suspended": ("active", "suspended"),
    "reactivated": ("suspended", "active"),
    "terminated": ("*", "terminated"),  # 任何 from
}


async def _fetch_status(tech_id: str, tenant_id: str) -> str:
    """取 technician status + tenant 隔離。CR-0103-fix：改用 technicians.tenant_id 直接判，
    不 JOIN users —— 原 JOIN users 在 user_id 為 NULL（admin 新增、舊資料）時撈不出列，
    導致核准/停權誤回 404 'not found in tenant'。technicians.tenant_id 為 NOT NULL 權威來源。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT status FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (tech_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"technician {tech_id} not found in tenant", 404)
    return row[0]


def _check_transition(current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot transition from '{current}' to '{target}'",
            409,
        )


async def _change_status_and_audit(
    *,
    tenant_id: str,
    tech_id: str,
    target_status: str,
    event_type: str,
    reason: str,
    notes: str | None,
    actor_user_id: str | None,
    actor_role: str | None,
) -> dict:
    """共用：fetch current → CAS UPDATE → INSERT audit row。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if not reason or len(reason.strip()) < 3:
        raise ApiError("VALIDATION_ERROR", "reason 至少 3 字元", 422)

    current = await _fetch_status(tech_id, tenant_id)
    _check_transition(current, target_status)

    conn = await db_module.require_tech_conn()
    upd = await conn.execute(
        "UPDATE technicians SET status = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = %s "
        "RETURNING id, status, updated_at",
        (target_status, tech_id, current),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)

    # 同步登入資格（2026-07-02 師傅測試修復）：technicians.status 是生命週期
    # source of truth，users.is_active 是登入/refresh 檢查點（A2 停權即時失效走
    # refresh 重查）。原本兩者脫鉤 → 停權/待核准技師仍可登入。active → 可登入；
    # 其他（pending_approval/suspended/terminated/rejected/inactive）→ 不可。
    cur = await conn.execute(
        "UPDATE users SET is_active = %s, updated_at = NOW() "
        "WHERE id = (SELECT user_id FROM technicians WHERE id = %s::uuid) "
        "  AND role = 'technician' "
        "RETURNING id",
        (target_status == "active", tech_id),
    )
    user_row = await cur.fetchone()

    # 投影鏡射(雙庫模式;fallback 為 no-op):停權/核准即時反映到品牌庫,
    # 供 load_user_security_state 與派工資格檢查續讀投影。
    await mirror_rows("technicians", [tech_id])
    if user_row:
        await mirror_rows("users", [str(user_row[0])])

    # audit row（best-effort：audit 失敗不 rollback status，但 log + warning）
    try:
        await conn.execute(
            "INSERT INTO saas.technician_lifecycle_event "
            "  (tenant_id, technician_id, event_type, previous_status, "
            "   new_status, reason, notes, actor_user_id, actor_role) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s)",
            (
                tenant_id, tech_id, event_type, current, target_status,
                reason.strip()[:500],
                notes.strip()[:1000] if notes else None,
                actor_user_id, actor_role,
            ),
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "tech lifecycle audit failed: tech=%s event=%s",
            tech_id[:8], event_type,
        )
    return {
        "technician_id": tech_id,
        "previous_status": current,
        "new_status": target_status,
        "event_type": event_type,
        "updated_at": row[2].isoformat() if row[2] else None,
    }


async def approve_onboarding(
    *, tenant_id: str, tech_id: str, actor_user_id: str,
    actor_role: str = "operations_manager", notes: str | None = None,
) -> dict:
    return await _change_status_and_audit(
        tenant_id=tenant_id, tech_id=tech_id,
        target_status="active", event_type="onboarding_approved",
        reason="onboarding approved by " + actor_role,
        notes=notes, actor_user_id=actor_user_id, actor_role=actor_role,
    )


async def reject_onboarding(
    *, tenant_id: str, tech_id: str, actor_user_id: str,
    reason: str, actor_role: str = "operations_manager",
    notes: str | None = None,
) -> dict:
    return await _change_status_and_audit(
        tenant_id=tenant_id, tech_id=tech_id,
        target_status="rejected", event_type="onboarding_rejected",
        reason=reason, notes=notes,
        actor_user_id=actor_user_id, actor_role=actor_role,
    )


_ORPHAN_WO_STATUSES = ("assigned", "accepted", "in_progress")


async def _active_work_orders(tech_id: str) -> list[str]:
    """CR-0164 E：查該技師名下進行中工單（品牌庫）——停權/終止前的孤兒偵測。

    work_orders 在品牌庫（db_module._conn）；technician_id 指品牌庫投影 id。回工單 id 清單。
    """
    if not await _ensure_conn():
        return []
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders WHERE technician_id = %s::uuid "
        "AND status = ANY(%s)",
        (tech_id, list(_ORPHAN_WO_STATUSES)),
    )
    return [str(r[0]) for r in await cur.fetchall()]


def _orphan_conflict(orphans: list[str], op: str) -> ApiError:
    return ApiError(
        "TECHNICIAN_HAS_ACTIVE_WORK_ORDERS",
        f"技師名下有 {len(orphans)} 張進行中工單，{op}前須先改派"
        f"（reassignWorkOrderV2）；工單：{', '.join(o[:8] for o in orphans[:5])}"
        + ("…" if len(orphans) > 5 else ""),
        409,
        details=[{"field": "work_order_id", "issue": o} for o in orphans],
    )


async def suspend(
    *, tenant_id: str, tech_id: str, actor_user_id: str,
    reason: str, actor_role: str = "operations_manager",
    notes: str | None = None, force: bool = False,
) -> dict:
    # CR-0164 E：孤兒工單軟阻擋——名下有進行中工單須先改派；主管帶 force 可越過
    # （緊急停權安全閥，孤兒仍在但已停權，須事後補改派）。
    if not force:
        orphans = await _active_work_orders(tech_id)
        if orphans:
            raise _orphan_conflict(orphans, "停權")
    return await _change_status_and_audit(
        tenant_id=tenant_id, tech_id=tech_id,
        target_status="suspended", event_type="suspended",
        reason=reason, notes=notes,
        actor_user_id=actor_user_id, actor_role=actor_role,
    )


async def reactivate(
    *, tenant_id: str, tech_id: str, actor_user_id: str,
    reason: str, actor_role: str = "operations_manager",
    notes: str | None = None,
) -> dict:
    return await _change_status_and_audit(
        tenant_id=tenant_id, tech_id=tech_id,
        target_status="active", event_type="reactivated",
        reason=reason, notes=notes,
        actor_user_id=actor_user_id, actor_role=actor_role,
    )


async def terminate(
    *, tenant_id: str, tech_id: str, actor_user_id: str,
    reason: str, actor_role: str = "operations_manager",
    notes: str | None = None,
) -> dict:
    """從任何 status → terminated 終態。"""
    # CR-0164 E：終止為終態、不可留孤兒——硬阻擋（無 force），名下進行中工單須先改派。
    orphans = await _active_work_orders(tech_id)
    if orphans:
        raise _orphan_conflict(orphans, "終止")
    return await _change_status_and_audit(
        tenant_id=tenant_id, tech_id=tech_id,
        target_status="terminated", event_type="terminated",
        reason=reason, notes=notes,
        actor_user_id=actor_user_id, actor_role=actor_role,
    )


# ============================================================
# Read — list events
# ============================================================

async def list_lifecycle_events(
    *,
    tenant_id: str,
    tech_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> dict:
    """列 lifecycle events，可選 tech_id + event_type filter。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if tech_id:
        where.append("technician_id = %s::uuid")
        args.append(tech_id)
    if event_type:
        where.append("event_type = %s")
        args.append(event_type)
    args.append(limit)

    conn = await db_module.require_tech_conn()  # lifecycle 事件單一居所在技師庫
    cur = await conn.execute(
        "SELECT id, technician_id, event_type, previous_status, new_status, "
        "       reason, notes, actor_user_id, actor_role, created_at "
        "FROM saas.technician_lifecycle_event "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "technician_id": str(r[1]),
            "event_type": r[2],
            "previous_status": r[3],
            "new_status": r[4],
            "reason": r[5],
            "notes": r[6],
            "actor_user_id": str(r[7]) if r[7] else None,
            "actor_role": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}
