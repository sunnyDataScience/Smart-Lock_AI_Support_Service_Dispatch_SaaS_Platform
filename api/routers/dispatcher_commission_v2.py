"""Dispatcher Commission v2 router — FR-0046 MVP 8 endpoints (對應 FR-0045)。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import dispatcher_commission_service as svc

logger = logging.getLogger("api.dispatcher_commission_v2")

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


class GenerateBody(BaseModel):
    dispatcher_user_id: str
    period_year: int
    period_month: int
    total_dispatched_orders: int = 0
    total_completed_orders: int = 0
    avg_customer_satisfaction: float | None = None
    base_commission: float = 0.0
    performance_bonus: float = 0.0
    penalty: float = 0.0
    notes: str | None = None


class DisputeBody(BaseModel):
    dispute_reason: str


class RejectBody(BaseModel):
    reason: str | None = None


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions:generate",
    operation_id="generateDispatcherCommission",
    summary="生成派工人 commission statement draft",
    response_model=dict, status_code=201,
)
async def generate(
    body: GenerateBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.generate_statement(
        tenant_id=tenantId, **body.model_dump(exclude_none=False),
    )}


@router.get(
    "/tenants/{tenantId}/dispatcher-commissions",
    operation_id="listDispatcherCommissions",
    summary="列 dispatcher commission statements (filter)",
    response_model=dict,
)
async def list_(
    tenantId: str = Path(...),
    dispatcher_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_statements(
        tenant_id=tenantId, dispatcher_user_id=dispatcher_user_id,
        status=status, limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}",
    operation_id="getDispatcherCommission",
    summary="取單筆 dispatcher commission statement",
    response_model=dict,
)
async def get_(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return {"data": await svc._get(statementId)}


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}:submit",
    operation_id="submitDispatcherCommissionForReview",
    summary="送 review (draft → pending_review) + 7d dispute window",
    response_model=dict,
)
async def submit(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.submit_for_review(statement_id=statementId)}


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}:dispute",
    operation_id="disputeDispatcherCommission",
    summary="派工人舉報異議 (pending_review → disputed)",
    response_model=dict,
)
async def dispute(
    body: DisputeBody,
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.dispute_statement(
        statement_id=statementId, dispute_reason=body.dispute_reason,
    )}


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}:approve",
    operation_id="approveDispatcherCommission",
    summary="主管核准 (pending_review → approved)",
    response_model=dict,
)
async def approve(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES, fail_closed=True)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.approve_statement(
        statement_id=statementId, reviewer_id=initiator,
    )}


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}:reject",
    operation_id="rejectDispatcherCommission",
    summary="主管退回 (pending_review|disputed → rejected)",
    response_model=dict,
)
async def reject(
    body: RejectBody,
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.reject_statement(
        statement_id=statementId, reviewer_id=initiator, reason=body.reason,
    )}


@router.post(
    "/tenants/{tenantId}/dispatcher-commissions/{statementId}:mark-paid",
    operation_id="markDispatcherCommissionPaid",
    summary="標已匯款 (approved → paid)",
    response_model=dict,
)
async def mark_paid(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES, fail_closed=True)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.mark_paid(statement_id=statementId)}
