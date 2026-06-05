"""SOP Feedback v2 router — FR-0051 MVP 3 endpoints。

1. POST /tenants/{tid}/sop-feedback             寫一條 feedback
2. GET  /tenants/{tid}/sop-feedback             list (filter)
3. GET  /tenants/{tid}/sop-feedback/{sopId}/summary  聚合單 SOP summary
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import sop_feedback_service as svc

logger = logging.getLogger("api.sop_feedback_v2")

router = APIRouter()


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


class FeedbackBody(BaseModel):
    sop_id: str
    sop_type: str
    source: str
    sentiment: str
    score: float | None = None
    comment: str | None = None
    metadata: dict | None = None
    reporter_user_id: str | None = None
    work_order_id: str | None = None


@router.post(
    "/tenants/{tenantId}/sop-feedback",
    operation_id="logSopFeedback",
    summary="寫 SOP feedback（多源：customer/technician/rma/ai/csm）",
    response_model=dict,
    status_code=201,
)
async def log_feedback(
    body: FeedbackBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.log_feedback(
        tenant_id=tenantId,
        **body.model_dump(exclude_none=False),
    )
    return {"data": result}


@router.get(
    "/tenants/{tenantId}/sop-feedback",
    operation_id="listSopFeedback",
    summary="列 SOP feedback (filter by sop_id/source/sentiment/date)",
    response_model=dict,
)
async def list_feedback(
    tenantId: str = Path(...),
    sop_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_feedback(
        tenant_id=tenantId, sop_id=sop_id, source=source,
        sentiment=sentiment, start_date=start_date, end_date=end_date,
        limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/sop-feedback/{sopId}/summary",
    operation_id="getSopFeedbackSummary",
    summary="聚合單 SOP feedback summary (by source / sentiment / sentiment_score)",
    response_model=dict,
)
async def get_summary(
    tenantId: str = Path(...),
    sopId: str = Path(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.get_sop_summary(
        tenant_id=tenantId, sop_id=sopId,
        start_date=start_date, end_date=end_date,
    )
