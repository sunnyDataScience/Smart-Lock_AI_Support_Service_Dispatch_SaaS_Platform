"""Technician Lifecycle v2 router — FR-0044 MVP 6 endpoints。

1-5. POST /tenants/{tid}/technicians/{techId}:onboard-approve / :onboard-reject /
                                          :suspend / :reactivate / :terminate
6.   GET  /tenants/{tid}/technicians/lifecycle-events?tech_id&event_type
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import DISPATCH_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import technician_lifecycle_service as svc

logger = logging.getLogger("api.technician_lifecycle_v2")

router = APIRouter()


async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


class ApproveBody(BaseModel):
    notes: str | None = None


class ReasonBody(BaseModel):
    reason: str
    notes: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. :onboard-approve   pending_approval → active
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/technicians/{technicianId}:onboard-approve",
    operation_id="approveTechnicianOnboarding",
    summary="師傅 onboarding 核准（pending_approval → active）",
    response_model=dict,
)
async def approve_onboarding(
    body: ApproveBody,
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.approve_onboarding(
        tenant_id=tenantId, tech_id=technicianId,
        actor_user_id=initiator, notes=body.notes,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 2. :onboard-reject   pending_approval → rejected
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/technicians/{technicianId}:onboard-reject",
    operation_id="rejectTechnicianOnboarding",
    summary="師傅 onboarding 拒絕（pending_approval → rejected）",
    response_model=dict,
)
async def reject_onboarding(
    body: ReasonBody,
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.reject_onboarding(
        tenant_id=tenantId, tech_id=technicianId,
        actor_user_id=initiator, reason=body.reason, notes=body.notes,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 3. :suspend   active → suspended
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/technicians/{technicianId}:suspend",
    operation_id="suspendTechnician",
    summary="師傅停權（active → suspended）",
    response_model=dict,
)
async def suspend_technician(
    body: ReasonBody,
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.suspend(
        tenant_id=tenantId, tech_id=technicianId,
        actor_user_id=initiator, reason=body.reason, notes=body.notes,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 4. :reactivate   suspended → active
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/technicians/{technicianId}:reactivate",
    operation_id="reactivateTechnician",
    summary="師傅復權（suspended → active）",
    response_model=dict,
)
async def reactivate_technician(
    body: ReasonBody,
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.reactivate(
        tenant_id=tenantId, tech_id=technicianId,
        actor_user_id=initiator, reason=body.reason, notes=body.notes,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 5. :terminate   任何 → terminated 終態
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/technicians/{technicianId}:terminate",
    operation_id="terminateTechnician",
    summary="師傅終止（任何 → terminated 終態）",
    response_model=dict,
)
async def terminate_technician(
    body: ReasonBody,
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.terminate(
        tenant_id=tenantId, tech_id=technicianId,
        actor_user_id=initiator, reason=body.reason, notes=body.notes,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 6. GET lifecycle events
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
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_lifecycle_events(
        tenant_id=tenantId, tech_id=tech_id,
        event_type=event_type, limit=limit,
    )
