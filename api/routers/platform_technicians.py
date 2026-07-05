"""Platform console 師傅審核 router(CR-0114 R3)。

裁決 1:師傅生命週期審核搬到平台方。全部 gate = require_platform_admin
(非 tenant-scoped);initiator 取已驗簽 token sub(廢除品牌端的自報
X-Initiator header,無偽造面)。

- GET  /platform/technicians?status=&q=
- POST /platform/technicians/{id}:onboard-approve / :onboard-reject /
                                  :suspend / :reactivate / :terminate
- GET  /platform/technicians/lifecycle-events?tech_id=&event_type=
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_platform_admin
from services import platform_technician_service as svc

logger = logging.getLogger("api.routers.platform_technicians")
router = APIRouter()


class ApproveBody(BaseModel):
    notes: str | None = None


class ReasonBody(BaseModel):
    reason: str
    notes: str | None = None


@router.get(
    "/platform/technicians",
    operation_id="listPlatformTechnicians",
    summary="跨品牌師傅清單(平台審核用)",
    status_code=200,
)
async def list_technicians(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_technicians(status=status, q=q)


@router.post(
    "/platform/technicians/{technicianId}:onboard-approve",
    operation_id="platformApproveTechnician",
    summary="師傅核准(pending_approval → active)",
    status_code=200,
)
async def approve(
    body: ApproveBody | None = None,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.approve_onboarding(
        tech_id=technicianId, actor_user_id=user.user_id,
        notes=(body.notes if body else None),
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:onboard-reject",
    operation_id="platformRejectTechnician",
    summary="師傅拒絕(pending_approval → rejected)",
    status_code=200,
)
async def reject(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.reject_onboarding(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:suspend",
    operation_id="platformSuspendTechnician",
    summary="師傅停權(active → suspended)",
    status_code=200,
)
async def suspend(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.suspend(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:reactivate",
    operation_id="platformReactivateTechnician",
    summary="師傅復權(suspended → active)",
    status_code=200,
)
async def reactivate(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.reactivate(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:terminate",
    operation_id="platformTerminateTechnician",
    summary="師傅終止(任何 → terminated 終態)",
    status_code=200,
)
async def terminate(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.terminate(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.get(
    "/platform/technicians/lifecycle-events",
    operation_id="listPlatformTechnicianLifecycleEvents",
    summary="跨品牌師傅 lifecycle audit",
    status_code=200,
)
async def list_lifecycle_events(
    tech_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_lifecycle_events(
        tech_id=tech_id, event_type=event_type, limit=limit,
    )
