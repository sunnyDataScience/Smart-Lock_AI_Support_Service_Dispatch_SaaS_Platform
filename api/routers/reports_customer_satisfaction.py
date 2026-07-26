"""Customer Satisfaction Report router — WBS §8 P2 KPI 擴充。

1 endpoint:
  GET /reports/customer-satisfaction?start_date=...&end_date=...
    → 客戶滿意度真實 metrics（avg_rating / rating_distribution /
       low_rating / 5-star / top_low_rating_recent）
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import customer_satisfaction_service as svc

logger = logging.getLogger("api.reports_customer_satisfaction")

router = APIRouter()


@router.get(
    "/reports/customer-satisfaction",
    operation_id="getCustomerSatisfactionReport",
    summary="客戶滿意度真實 metrics（avg / distribution / 低分率 / top 低分案例）",
    response_model=dict,
)
async def get_customer_satisfaction_report(
    start_date: date | None = Query(
        default=None,
        description="統計起日（含）；與 end_date 搭配。未給 = 全時段聚合。",
    ),
    end_date: date | None = Query(
        default=None,
        description="統計迄日（含）；與 start_date 搭配。",
    ),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    if (start_date is None) != (end_date is None):
        raise ApiError(
            "VALIDATION_ERROR",
            "start_date 與 end_date 必須同時給或同時不給",
            422,
        )
    if start_date and end_date and start_date > end_date:
        raise ApiError(
            "VALIDATION_ERROR", "start_date must <= end_date", 422,
        )
    return await svc.get_customer_satisfaction(
        tenant_id=user.tenant_id,
        start_date=start_date, end_date=end_date,
    )
