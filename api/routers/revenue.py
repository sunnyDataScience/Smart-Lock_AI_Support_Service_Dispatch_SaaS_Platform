"""Revenue 報表 router — getRevenueSummary (read-only)。

operationId 對齊 openapi.yaml：getRevenueSummary

不含 CSV/Excel 匯出端點（前端按鈕 stay-disabled 至寫入路徑接入）。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
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
    start_date: date | None = Query(
        default=None,
        description="統計起日（含），落點以 invoices.issued_at 為準（draft 走 created_at）。",
    ),
    end_date: date | None = Query(
        default=None,
        description="統計迄日（含），與 start_date 搭配使用。",
    ),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    summary = await revenue_service.get_revenue_summary(
        tenant_id=user.tenant_id,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )
    return RevenueSummary(**summary).model_dump(mode="json")
