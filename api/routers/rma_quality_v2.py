"""RMA Quality Feedback v2 router — FR-0048 MVP 4 endpoints。

1. POST /tenants/{tid}/rma-quality-findings                 寫 finding
2. GET  /tenants/{tid}/rma-quality-findings                 list (filter)
3. GET  /tenants/{tid}/rma-quality-findings/brand-summary   cascade (a) 品牌商
4. GET  /tenants/{tid}/rma-quality-findings/technicians/{techId}/summary cascade (b) 技師
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, OPS_ROLES, require_tenant, role_required
from core.errors import ApiError
from services import rma_quality_service as svc

logger = logging.getLogger("api.rma_quality_v2")

router = APIRouter()


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


class FindingBody(BaseModel):
    failure_mode: str
    warranty_claim_id: str | None = None
    work_order_id: str | None = None
    technician_id: str | None = None
    brand: str | None = None
    device_model: str | None = None
    root_cause: str | None = None
    is_repeat_failure: bool = False
    brand_quality_score: float | None = None
    technician_quality_score: float | None = None
    ai_diagnosis_accuracy: str | None = None
    customer_satisfaction_score: float | None = None
    reported_by_user_id: str | None = None
    notes: str | None = None
    propagate_to_sop_feedback_sop_id: str | None = None
    propagate_to_sop_feedback_sop_type: str | None = None


@router.post(
    "/tenants/{tenantId}/rma-quality-findings",
    operation_id="logRmaQualityFinding",
    summary="寫 RMA 品質訊號 + 可選 cascade 到 SOP feedback",
    response_model=dict,
    status_code=201,
)
async def log_finding(
    body: FindingBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.log_finding(
        tenant_id=tenantId,
        **body.model_dump(exclude_none=False),
    )
    return {"data": result}


@router.get(
    "/tenants/{tenantId}/rma-quality-findings",
    operation_id="listRmaQualityFindings",
    summary="列 RMA quality findings (filter)",
    response_model=dict,
)
async def list_findings(
    tenantId: str = Path(...),
    failure_mode: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    technician_id: str | None = Query(default=None),
    is_repeat_failure: bool | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_findings(
        tenant_id=tenantId, failure_mode=failure_mode, brand=brand,
        technician_id=technician_id, is_repeat_failure=is_repeat_failure,
        start_date=start_date, end_date=end_date, limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/rma-quality-findings/brand-summary",
    operation_id="getRmaQualityBrandSummary",
    summary="Cascade (a) 品牌商視角 summary (top failure_modes / brand_quality avg)",
    response_model=dict,
)
async def brand_summary(
    tenantId: str = Path(...),
    brand: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.get_brand_summary(
        tenant_id=tenantId, brand=brand,
        start_date=start_date, end_date=end_date,
    )


@router.get(
    "/tenants/{tenantId}/rma-quality-findings/technicians/{technicianId}/summary",
    operation_id="getRmaQualityTechnicianSummary",
    summary="Cascade (b) 技師視角 summary (technician_quality avg / repeat rate)",
    response_model=dict,
)
async def technician_summary(
    tenantId: str = Path(...),
    technicianId: str = Path(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.get_technician_summary(
        tenant_id=tenantId, technician_id=technicianId,
        start_date=start_date, end_date=end_date,
    )
