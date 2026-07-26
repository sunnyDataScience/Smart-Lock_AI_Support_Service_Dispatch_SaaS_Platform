"""Technician Lifecycle v2 router — 品牌端唯讀 audit(CR-0114 R3)。

**寫端點已搬到平台方 console**(裁決 1):師傅生命週期審核(核准/拒絕/停權/
復權/終止)不再由品牌後台操作,改由 platform console
(POST /api/v1/platform/technicians/{id}:onboard-approve 等,
routers/platform_technicians.py)。師傅身分庫全平台唯一,審核歸平台方統一管。

品牌端只保留這支唯讀 audit(讓品牌看到旗下師傅的生命週期歷史):
6. GET /tenants/{tid}/technicians/lifecycle-events?tech_id&event_type
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import technician_lifecycle_service as svc

logger = logging.getLogger("api.technician_lifecycle_v2")

router = APIRouter()


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


# ─────────────────────────────────────────────────────────────────────────────
# GET lifecycle events（品牌端唯讀;寫端點見 platform_technicians.py）
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/technicians/lifecycle-events",
    operation_id="listTechnicianLifecycleEvents",
    summary="列師傅 lifecycle audit events（可選 tech_id + event_type filter）",
    response_model=dict,
)
async def list_lifecycle_events(
    tenantId: str = Path(...),
    tech_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_lifecycle_events(
        tenant_id=tenantId, tech_id=tech_id,
        event_type=event_type, limit=limit,
    )
