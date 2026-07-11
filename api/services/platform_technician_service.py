"""平台方師傅審核服務(CR-0114 R3)。

裁決 1:師傅生命週期審核(核准/拒絕/停權/復權/終止)自品牌後台搬到平台
console。師傅身分庫全平台唯一 → 平台端直查 authority(require_tech_conn),
天然涵蓋全品牌,不需 tenant scope。

實作策略:**復用 technician_lifecycle_service 狀態機零改動**。該 service 的
wrapper 需要 tenant_id(用於 _fetch_status 隔離與 audit row)→ 平台端點先查
該師傅的 tenant_id(authority)再轉呼叫;actor_role 帶 'platform_admin'、
actor_user_id 取已驗簽 token sub(比品牌端「前端自報 X-Initiator」更強)。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.errors import ApiError
from services import technician_lifecycle_service as lifecycle_svc
from services import technician_service
from services import technician_certification_service as cert_service

logger = logging.getLogger("api.platform_technician")

_ACTOR_ROLE = "platform_admin"

# 平台建立師傅的預設租戶(師傅身分庫全平台共用;對齊 auth_service.register_technician
# 與舊品牌 create_technician 的 tenant 指派 —— 師傅仍掛預設租戶,派工授權另由
# technician_brand_authorization 管理)。
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# 平台審核師傅清單欄位(authority technicians JOIN users 取登入態)
_LIST_SELECT = (
    "t.id, t.tenant_id, t.name, t.phone, t.email, t.status, "
    "t.capabilities, t.service_regions, t.created_at, u.is_active"
)


def _list_row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]) if row[1] else None,
        "name": row[2] or "",
        "phone": row[3] or "",
        "email": row[4] or "",
        "status": row[5],
        "capabilities": row[6] if isinstance(row[6], list) else [],
        "service_regions": row[7] if isinstance(row[7], list) else [],
        "created_at": row[8].isoformat() if row[8] else None,
        "is_active": row[9],
    }


async def list_technicians(status: str | None = None, q: str | None = None) -> dict:
    """跨品牌師傅清單(直查 authority)。status 過濾 + q 模糊(name/phone/email)。"""
    conn = await db_module.require_tech_conn()
    where: list[str] = []
    args: list = []
    if status:
        where.append("t.status = %s")
        args.append(status)
    if q:
        where.append("(t.name ILIKE %s OR t.phone ILIKE %s OR t.email ILIKE %s)")
        like = f"%{q}%"
        args.extend([like, like, like])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    cur = await conn.execute(
        f"SELECT {_LIST_SELECT} FROM technicians t "
        "LEFT JOIN users u ON u.id = t.user_id "
        f"{where_sql} ORDER BY t.created_at DESC LIMIT 200",
        tuple(args),
    )
    rows = await cur.fetchall()
    return {"data": [_list_row_to_dict(r) for r in rows], "message": None}


async def _resolve_tenant_id(tech_id: str) -> str:
    """查該師傅的 tenant_id(authority);不存在 → 404。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT tenant_id FROM technicians WHERE id = %s::uuid", (tech_id,))
    row = await cur.fetchone()
    if not row or not row[0]:
        raise ApiError("NOT_FOUND", f"technician {tech_id} not found", 404)
    return str(row[0])


async def approve_onboarding(*, tech_id: str, actor_user_id: str, notes: str | None = None) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await lifecycle_svc.approve_onboarding(
        tenant_id=tenant_id, tech_id=tech_id,
        actor_user_id=actor_user_id, actor_role=_ACTOR_ROLE, notes=notes,
    )


async def reject_onboarding(
    *, tech_id: str, actor_user_id: str, reason: str, notes: str | None = None
) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await lifecycle_svc.reject_onboarding(
        tenant_id=tenant_id, tech_id=tech_id, actor_user_id=actor_user_id,
        actor_role=_ACTOR_ROLE, reason=reason, notes=notes,
    )


async def suspend(*, tech_id: str, actor_user_id: str, reason: str,
                  notes: str | None = None, force: bool = False) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await lifecycle_svc.suspend(
        tenant_id=tenant_id, tech_id=tech_id, actor_user_id=actor_user_id,
        actor_role=_ACTOR_ROLE, reason=reason, notes=notes, force=force,
    )


async def reactivate(*, tech_id: str, actor_user_id: str, reason: str, notes: str | None = None) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await lifecycle_svc.reactivate(
        tenant_id=tenant_id, tech_id=tech_id, actor_user_id=actor_user_id,
        actor_role=_ACTOR_ROLE, reason=reason, notes=notes,
    )


async def terminate(*, tech_id: str, actor_user_id: str, reason: str, notes: str | None = None) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await lifecycle_svc.terminate(
        tenant_id=tenant_id, tech_id=tech_id, actor_user_id=actor_user_id,
        actor_role=_ACTOR_ROLE, reason=reason, notes=notes,
    )


async def list_lifecycle_events(
    *, tech_id: str | None = None, event_type: str | None = None, limit: int = 50
) -> dict:
    """跨品牌 lifecycle audit(不強制 tenant filter;平台全域視角)。"""
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)
    conn = await db_module.require_tech_conn()  # 事件單一居所在技師庫
    where: list[str] = []
    args: list = []
    if tech_id:
        where.append("technician_id = %s::uuid")
        args.append(tech_id)
    if event_type:
        where.append("event_type = %s")
        args.append(event_type)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    args.append(limit)
    cur = await conn.execute(
        "SELECT id, technician_id, event_type, previous_status, new_status, "
        "       reason, notes, actor_user_id, actor_role, created_at "
        "FROM saas.technician_lifecycle_event "
        f"{where_sql} ORDER BY created_at DESC LIMIT %s",
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
    return {"data": items, "message": None}

# ─────────────────────────────────────────────────────────────────────────────
# 師傅管理（CR-0114 §8 追補「platform console 補師傅建立/編輯/認證管理」收尾）
# 復用師傅身分域 service（technician_service / technician_certification_service），
# 平台端解析 tenant 後轉呼叫（跨品牌）；治理在 route 層（require_platform_admin），
# 品牌端寫端點仍不存在。
# ─────────────────────────────────────────────────────────────────────────────


async def get_technician_detail(*, tech_id: str) -> dict:
    """單筆師傅詳情（身分域完整欄位 + authorized_brands）。"""
    tenant_id = await _resolve_tenant_id(tech_id)
    return await technician_service.get_technician(
        tenant_id=tenant_id, technician_id=tech_id
    )


async def create_technician(
    *,
    display_name: str,
    coverage_areas: list[str],
    phone: str | None = None,
    email: str | None = None,
    capabilities: list[str] | None = None,
) -> tuple[dict, bool]:
    """平台手動 onboard 新師傅（掛預設租戶,status=pending_approval,待核准）。"""
    return await technician_service.create_technician(
        tenant_id=_DEFAULT_TENANT_ID,
        display_name=display_name,
        coverage_areas=coverage_areas,
        phone=phone,
        email=email,
        capabilities=capabilities,
    )


async def update_technician(*, tech_id: str, patch: dict) -> dict:
    """編輯師傅主檔（name/phone/email/capabilities/regions/level）。"""
    tenant_id = await _resolve_tenant_id(tech_id)
    return await technician_service.update_technician(
        tenant_id=tenant_id, technician_id=tech_id, patch=patch
    )


async def list_certifications(*, tech_id: str) -> list[dict]:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await cert_service.list_certifications(
        tenant_id=tenant_id, technician_id=tech_id
    )


async def create_certification(
    *, tech_id: str, cert_name: str, brand: str | None = None,
    obtained_at: str | None = None, expires_at: str | None = None,
) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await cert_service.create_certification(
        tenant_id=tenant_id, technician_id=tech_id, cert_name=cert_name,
        brand=brand, obtained_at=obtained_at, expires_at=expires_at,
    )


async def update_certification(*, tech_id: str, cert_id: str, patch: dict) -> dict:
    tenant_id = await _resolve_tenant_id(tech_id)
    return await cert_service.update_certification(
        tenant_id=tenant_id, technician_id=tech_id, cert_id=cert_id, patch=patch
    )


async def delete_certification(*, tech_id: str, cert_id: str) -> None:
    tenant_id = await _resolve_tenant_id(tech_id)
    await cert_service.delete_certification(
        tenant_id=tenant_id, technician_id=tech_id, cert_id=cert_id
    )
