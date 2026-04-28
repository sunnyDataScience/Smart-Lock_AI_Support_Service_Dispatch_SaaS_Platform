"""Revenue 報表 router — getRevenueSummary (read-only)。

operationId 對齊 openapi.yaml：getRevenueSummary

不含 CSV/Excel 匯出端點（前端按鈕 stay-disabled 至寫入路徑接入）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import RevenueSummary
from services import revenue_service

router = APIRouter()


@router.get(
    "/reports/revenue",
    operation_id="getRevenueSummary",
    summary="營收彙整（KPI + 月度趨勢 + 品牌占比）",
    response_model=RevenueSummary,
)
async def get_revenue_summary(
    granularity: str = Query(default="month"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    summary = await revenue_service.get_revenue_summary(
        tenant_id=user.tenant_id,
        granularity=granularity,
    )
    return RevenueSummary(**summary).model_dump(mode="json")
