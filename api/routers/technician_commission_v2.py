"""Technician Commission v2 router — CR-0106 師傅佣金月結（tenant-scoped）。

  - GET /tenants/{tenantId}/technicians/{techId}/commission-summary?year=&month=

師傅詳情頁右欄「佣金摘要」真資料來源（取代抽成制 mock）。base_payout 為內部敏感成本，
故限 DISPATCH_ROLES（admin/ops/dispatcher）；技師本人查自己薪資走 me-scoped 端點（另議）。
year/month 預設當月。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from core.deps import DISPATCH_ROLES, CurrentUser, role_required
from core.errors import ApiError
from services import technician_commission_service as commission_service

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/technicians/{techId}/commission-summary",
    operation_id="getTechnicianCommissionSummary",
    summary="師傅佣金月結摘要（固定工資制，tenant-scoped，admin 視角）",
    tags=["M05 Technician"],
)
async def get_commission_summary(
    tenantId: str = Path(...),
    techId: str = Path(...),
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    today = date.today()
    summary = await commission_service.compute_monthly_commission(
        tenant_id=tenantId,
        technician_id=techId,
        year=year or today.year,
        month=month or today.month,
    )
    return {"data": summary}
