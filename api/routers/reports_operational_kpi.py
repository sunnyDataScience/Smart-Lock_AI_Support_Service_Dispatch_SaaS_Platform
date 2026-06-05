"""Operational KPI Report router — WBS §8 P2 完整收尾。

1 endpoint:
  GET /reports/operational-kpi?start_date&end_date
    → FTFR + SLA 達成率 (dispatch / arrival on-time)
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import operational_kpi_service as svc

logger = logging.getLogger("api.reports_operational_kpi")

router = APIRouter()


@router.get(
    "/reports/operational-kpi",
    operation_id="getOperationalKpiReport",
    summary="Operational KPI（FTFR + SLA on-time dispatch / arrival 達成率）",
    response_model=dict,
)
async def get_operational_kpi_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
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
    return await svc.get_operational_kpi(
        tenant_id=user.tenant_id,
        start_date=start_date, end_date=end_date,
    )
