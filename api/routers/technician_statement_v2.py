"""Technician AP Statement v2 router — FR-0045 MVP 7 endpoints。

1. POST :generate                                生成 draft (admin/cron)
2. GET  list                                     列 statements (filter)
3. GET  {id}                                     取單筆
4. POST {id}:submit                              draft → pending_review
5. POST {id}:dispute                             pending_review → disputed (技師)
6. POST {id}:approve                             pending_review → approved (主管)
7. POST {id}:reject                              pending_review|disputed → rejected
8. POST {id}:mark-paid                           approved → paid
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import technician_statement_service as svc

logger = logging.getLogger("api.technician_statement_v2")

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
    technician_id: str
    period_year: int
    period_month: int
    # CR-0117 S4：gross / 完工單數省略 = 系統依 CR-0106 佣金口徑自動計算；帶值 = 人工覆寫
    gross_amount: float | None = None
    travel_fee_deduction: float = 0.0
    cash_collection_deduction: float = 0.0
    dispute_hold_amount: float = 0.0
    other_deductions: float = 0.0
    total_completed_orders: int | None = None
    notes: str | None = None


class DisputeBody(BaseModel):
    dispute_reason: str


class RejectBody(BaseModel):
    reason: str | None = None


@router.post(
    "/tenants/{tenantId}/tech-statements:generate",
    operation_id="generateTechStatement",
    summary="生成技師月結 statement draft",
    response_model=dict,
    status_code=201,
)
async def generate(
    body: GenerateBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.generate_statement(
        tenant_id=tenantId, **body.model_dump(exclude_none=False),
    )
    return {"data": result}


@router.get(
    "/tenants/{tenantId}/tech-statements",
    operation_id="listTechStatements",
    summary="列 statements (filter)",
    response_model=dict,
)
async def list_(
    tenantId: str = Path(...),
    technician_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_statements(
        tenant_id=tenantId, technician_id=technician_id,
        status=status, limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/tech-statements/{statementId}",
    operation_id="getTechStatement",
    summary="取單筆 statement",
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
    "/tenants/{tenantId}/tech-statements/{statementId}:submit",
    operation_id="submitTechStatementForReview",
    summary="送 review (draft → pending_review) + 設 dispute window 7d",
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
    "/tenants/{tenantId}/tech-statements/{statementId}:dispute",
    operation_id="disputeTechStatement",
    summary="技師舉報異議 (pending_review → disputed)",
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
    return {
        "data": await svc.dispute_statement(
            statement_id=statementId, dispute_reason=body.dispute_reason,
        ),
    }


@router.post(
    "/tenants/{tenantId}/tech-statements/{statementId}:approve",
    operation_id="approveTechStatement",
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
    return {
        "data": await svc.approve_statement(
            statement_id=statementId, reviewer_id=initiator,
        ),
    }


@router.post(
    "/tenants/{tenantId}/tech-statements/{statementId}:reject",
    operation_id="rejectTechStatement",
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
    return {
        "data": await svc.reject_statement(
            statement_id=statementId, reviewer_id=initiator,
            reason=body.reason,
        ),
    }


@router.post(
    "/tenants/{tenantId}/tech-statements/{statementId}:mark-paid",
    operation_id="markTechStatementPaid",
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
