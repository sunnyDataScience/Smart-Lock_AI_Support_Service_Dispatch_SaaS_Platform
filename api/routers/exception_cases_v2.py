"""CR-0041 M15 異常框架 router — exception_case lifecycle（tenant-scoped）。

真 M15 異常 control tower（與誤命名的 exceptions_v2.py〔實為師傅排班〕區隔）：
  POST   /tenants/{tid}/exception-cases               開異常
  GET    /tenants/{tid}/exception-cases               列異常（status/severity filter）
  GET    /tenants/{tid}/exception-cases/{id}          單筆
  POST   /tenants/{tid}/exception-cases/{id}:resolve  處理（選 return_path）
  POST   /tenants/{tid}/exception-cases/{id}:escalate 升級

require_tenant + cross-tenant guard（ADR-0030）；resolve/escalate 限管理角色。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import exception_service

router = APIRouter()

_resolve_roles = role_required(
    "admin", "operations_manager", "dispatcher", "customer_service"
)


def _guard(user: CurrentUser, tenantId: str) -> None:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId does not match authenticated tenant", 403)


class _OpenExceptionRequest(BaseModel):
    exception_type: str = Field(..., description="ExceptionType 10 值之一")
    work_order_id: str | None = None
    severity: str = Field(default="medium", description="low/medium/high/critical")
    description: str | None = Field(default=None, max_length=2000)


class _ResolveExceptionRequest(BaseModel):
    return_path: str = Field(..., description="continue/requote/reschedule/reassign/new_wo/cancel/refund/rma/dispute")
    resolution: str | None = Field(default=None, max_length=2000)
    return_to_stage: str | None = None


@router.post(
    "/tenants/{tenantId}/exception-cases",
    operation_id="openExceptionCase",
    summary="開立異常案件 v2（M15 control tower；high/critical + WO → high_risk_hold）",
    status_code=201,
    tags=["M15 Exception"],
)
async def open_exception_case(
    body: _OpenExceptionRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(_resolve_roles),
) -> dict:
    _guard(user, tenantId)
    return await exception_service.open_exception(
        tenant_id=tenantId,
        exception_type=body.exception_type,
        work_order_id=body.work_order_id,
        severity=body.severity,
        description=body.description,
        created_by=user.user_id,
    )


@router.get(
    "/tenants/{tenantId}/exception-cases",
    operation_id="listExceptionCases",
    summary="列異常案件 v2（status/severity/work_order_id filter）",
    tags=["M15 Exception"],
)
async def list_exception_cases(
    tenantId: str = Path(...),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard(user, tenantId)
    return await exception_service.list_exceptions(
        tenant_id=tenantId,
        status=status,
        severity=severity,
        work_order_id=work_order_id,
        limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/exception-cases/{exceptionId}",
    operation_id="getExceptionCase",
    summary="單筆異常案件 v2",
    tags=["M15 Exception"],
)
async def get_exception_case(
    tenantId: str = Path(...),
    exceptionId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard(user, tenantId)
    return await exception_service.get_exception(tenant_id=tenantId, exception_id=exceptionId)


@router.post(
    "/tenants/{tenantId}/exception-cases/{exceptionId}:resolve",
    operation_id="resolveExceptionCase",
    summary="處理異常 v2（選 return_path；解除 high_risk_hold）",
    tags=["M15 Exception"],
)
async def resolve_exception_case(
    body: _ResolveExceptionRequest,
    tenantId: str = Path(...),
    exceptionId: str = Path(...),
    user: CurrentUser = Depends(_resolve_roles),
) -> dict:
    _guard(user, tenantId)
    return await exception_service.resolve_exception(
        tenant_id=tenantId,
        exception_id=exceptionId,
        return_path=body.return_path,
        resolution=body.resolution,
        return_to_stage=body.return_to_stage,
        resolved_by=user.user_id,
    )


@router.post(
    "/tenants/{tenantId}/exception-cases/{exceptionId}:escalate",
    operation_id="escalateExceptionCase",
    summary="升級異常 v2",
    tags=["M15 Exception"],
)
async def escalate_exception_case(
    tenantId: str = Path(...),
    exceptionId: str = Path(...),
    user: CurrentUser = Depends(_resolve_roles),
) -> dict:
    _guard(user, tenantId)
    return await exception_service.escalate_exception(
        tenant_id=tenantId, exception_id=exceptionId
    )
