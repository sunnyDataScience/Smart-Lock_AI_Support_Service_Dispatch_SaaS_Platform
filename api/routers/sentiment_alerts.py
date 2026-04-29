"""Sentiment Alerts router — listSentimentAlerts endpoint。

operationId 對齊 openapi.yaml：listSentimentAlerts
租戶隔離透過 JOIN conversations → users.tenant_id。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import SentimentAlert, SentimentAlertPage, SentimentAlertStatus
from services import sentiment_service

router = APIRouter()


@router.get(
    "/sentiment/alerts",
    operation_id="listSentimentAlerts",
    summary="負面情緒告警列表（cursor 分頁，可依 status / start_time 過濾）",
    response_model=SentimentAlertPage,
)
async def list_sentiment_alerts(
    status: SentimentAlertStatus | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await sentiment_service.list_alerts(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        start_time=start_time,
    )
    return {
        "items": [SentimentAlert(**a).model_dump(mode="json") for a in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
