"""Sentiment Alerts router — listSentimentAlerts + updateSentimentAlert。

operationId 對齊 openapi.yaml：listSentimentAlerts, updateSentimentAlert
租戶隔離透過 JOIN conversations → users.tenant_id。
狀態機（見 services.sentiment_service._STATUS_TRANSITIONS）：
    pending → acknowledged → resolved（單向，違規回 409）
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    SentimentAlert,
    SentimentAlertPage,
    SentimentAlertStatus,
    SentimentAlertUpdateRequest,
)
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
    # CR-0183 補漏（2026-07-27）：v2 孿生端點已上守衛、本 legacy 端點漏掛，
    # 兩者皆掛載 → 低權限角色改打 legacy 路徑即可繞過。對齊 v2 守衛。
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
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


@router.patch(
    "/sentiment/alerts/{alert_id}",
    operation_id="updateSentimentAlert",
    summary="處理情緒告警（pending → acknowledged → resolved）",
    response_model=SentimentAlert,
)
async def update_sentiment_alert(
    payload: SentimentAlertUpdateRequest,
    alert_id: str = Path(),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    alert = await sentiment_service.update_alert(
        tenant_id=user.tenant_id,
        alert_id=alert_id,
        status=payload.status.value,
        admin_note=payload.admin_note,
    )
    body = SentimentAlert(**alert).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, body)
    return body
