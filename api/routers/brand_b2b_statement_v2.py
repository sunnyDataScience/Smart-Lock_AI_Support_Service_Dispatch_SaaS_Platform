"""Brand B2B Settlement v2 router — FR-0047 MVP 8 endpoints。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import brand_b2b_statement_service as svc

logger = logging.getLogger("api.brand_b2b_statement_v2")

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
    brand_partner_id: str
    brand_name: str
    period_year: int
    period_month: int
    direction: str = "NET"
    contract_ref: str | None = None
    total_service_orders: int = 0
    total_warranty_claims: int = 0
    sla_breach_count: int = 0
    ar_service_fee: float = 0.0
    ap_commission: float = 0.0
    warranty_deduction: float = 0.0
    sla_penalty: float = 0.0
    notes: str | None = None


class DisputeBody(BaseModel):
    dispute_reason: str


class RejectBody(BaseModel):
    reason: str | None = None


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements:generate",
    operation_id="generateBrandB2bStatement",
    summary="生成品牌 B2B settlement draft (AR/AP/NET)",
    response_model=dict, status_code=201,
)
async def generate(
    body: GenerateBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.generate_statement(
        tenant_id=tenantId, **body.model_dump(exclude_none=False),
    )}


@router.get(
    "/tenants/{tenantId}/brand-b2b-statements",
    operation_id="listBrandB2bStatements",
    summary="列 brand B2B statements (filter)",
    response_model=dict,
)
async def list_(
    tenantId: str = Path(...),
    brand_partner_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_statements(
        tenant_id=tenantId, brand_partner_id=brand_partner_id,
        direction=direction, status=status, limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}",
    operation_id="getBrandB2bStatement",
    summary="取單筆 brand B2B statement",
    response_model=dict,
)
async def get_(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return {"data": await svc._get(statementId)}


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}:submit",
    operation_id="submitBrandB2bStatementForReview",
    summary="送 review (draft → pending_review) + 7d dispute window",
    response_model=dict,
)
async def submit(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.submit_for_review(statement_id=statementId)}


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}:dispute",
    operation_id="disputeBrandB2bStatement",
    summary="品牌方舉報異議 (pending_review → disputed)",
    response_model=dict,
)
async def dispute(
    body: DisputeBody,
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.dispute_statement(
        statement_id=statementId, dispute_reason=body.dispute_reason,
    )}


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}:approve",
    operation_id="approveBrandB2bStatement",
    summary="主管核准 (pending_review → approved)",
    response_model=dict,
)
async def approve(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.approve_statement(
        statement_id=statementId, reviewer_id=initiator,
    )}


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}:reject",
    operation_id="rejectBrandB2bStatement",
    summary="主管退回 (pending_review|disputed → rejected)",
    response_model=dict,
)
async def reject(
    body: RejectBody,
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.reject_statement(
        statement_id=statementId, reviewer_id=initiator, reason=body.reason,
    )}


@router.post(
    "/tenants/{tenantId}/brand-b2b-statements/{statementId}:mark-paid",
    operation_id="markBrandB2bStatementPaid",
    summary="標已結算 (approved → paid)",
    response_model=dict,
)
async def mark_paid(
    tenantId: str = Path(...),
    statementId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return {"data": await svc.mark_paid(statement_id=statementId)}
