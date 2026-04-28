"""Dashboard router — 1 endpoint。

operationId 對齊 openapi.yaml：getDashboardStats。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import DashboardPeriod, DashboardStats
from services import dashboard_service

router = APIRouter()


@router.get(
    "/dashboard/stats",
    operation_id="getDashboardStats",
    summary="Dashboard 統計（period: today/7d/30d/90d）",
    response_model=DashboardStats,
)
async def get_dashboard_stats(
    period: DashboardPeriod = Query(default=DashboardPeriod.field_7d),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    stats = await dashboard_service.get_stats(
        tenant_id=user.tenant_id,
        period=period.value,
    )
    return DashboardStats(**stats).model_dump(mode="json")
