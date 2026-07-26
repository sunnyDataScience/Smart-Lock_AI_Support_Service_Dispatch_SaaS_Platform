"""Dashboard v2 router — tenant-scoped 統計端點（CR-0003 P2-W1 / FR-0021）。

對齊 frozen spec §FR-0021 Dashboard/報表：
  - GET /tenants/{tenantId}/dashboard/stats → getDashboardStatsV2

舊路徑 /api/v1/dashboard/stats（routers/dashboard.py）仍保留，
加掛 Deprecation header（D3 DeprecationMiddleware）雙掛過渡。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 dashboard_service.get_stats()，不重寫 SQL
  - 回傳 DashboardStats model（對齊 generated schema）
  - read-only GET（無 idempotency 需求）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import DashboardPeriod, DashboardStats
from services import dashboard_service

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/dashboard/stats",
    operation_id="getDashboardStatsV2",
    summary="Dashboard 統計 v2（tenant-scoped，period: today/7d/30d/90d）",
    response_model=DashboardStats,
    tags=["Dashboard"],
)
async def get_dashboard_stats_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    period: DashboardPeriod = Query(
        default=DashboardPeriod.field_7d,
        description="統計時段：today / 7d / 30d / 90d",
    ),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    stats = await dashboard_service.get_stats(
        tenant_id=tenantId,
        period=period.value,
    )
    return DashboardStats(**stats).model_dump(mode="json")
