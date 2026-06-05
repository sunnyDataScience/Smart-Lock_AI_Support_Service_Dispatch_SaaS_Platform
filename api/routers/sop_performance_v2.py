"""SOP Performance v2 router — WBS §8 P1 真實化（取代前端 placeholder「開發中」）。

1 endpoint:
  GET /tenants/{tenantId}/sop-performance/metrics?window_days=30
    → SOP 績效真實聚合 metrics
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import sop_performance_service as svc

logger = logging.getLogger("api.sop_performance_v2")

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/sop-performance/metrics",
    operation_id="getSopPerformanceMetrics",
    summary="SOP 績效真實 metrics（status / rates / 30 日 window / top / retire 候選）",
    response_model=dict,
)
async def get_sop_metrics(
    tenantId: str = Path(...),
    window_days: int = Query(default=30, ge=1, le=365),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await svc.get_sop_metrics(
        tenant_id=tenantId, window_days=window_days,
    )
