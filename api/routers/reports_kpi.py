"""KPI Report router — getKpiReport (read-only)。

operationId 對齊 openapi.yaml：getKpiReport。

未來擴充（不在本 phase 範圍）：
  - SLA 達成率（需 SLA 規則表 + tracker）
  - 客戶滿意度 / NPS / 差評率（需評價回傳機制）
  - FTFR（rework_of_id 已存在但需業務邏輯確認）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import DashboardPeriod, KpiReport
from services import kpi_service

router = APIRouter()


@router.get(
    "/reports/kpi",
    operation_id="getKpiReport",
    summary="KPI 儀表板（漏斗 / 異常率 / 技師效率；read-only）",
    response_model=KpiReport,
)
async def get_kpi_report(
    period: DashboardPeriod = Query(default=DashboardPeriod.field_30d),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    report = await kpi_service.get_kpi_report(
        tenant_id=user.tenant_id,
        period=period.value,
    )
    return KpiReport(**report).model_dump(mode="json")
