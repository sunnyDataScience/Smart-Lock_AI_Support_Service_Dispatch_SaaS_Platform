"""Sentiment Alerts v2 — tenant-scoped（CR-0003 P2-W2, FR-0018 / ADR-0048 handoff）。

spec 對齊：
  GET  /tenants/{tenantId}/sentiment/alerts           → listSentimentAlerts（v2）
  PATCH /tenants/{tenantId}/sentiment/alerts/{id}     → updateSentimentAlert（v2）

設計原則：
  - tenant-scoped path（非 /api/v1 flat）
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard on PATCH（HTTP Idempotency-Key header，依 W1 教訓）
  - 呼既有 sentiment_service（list_alerts / update_alert），零業務邏輯重寫
  - response_model 型別與 service 輸出相符（W1 教訓：SentimentAlert not SentimentAlertPage）

舊 flat 路徑（routers/sentiment_alerts.py）保留過渡期雙掛，前端遷移後移除。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
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
    "/tenants/{tenantId}/sentiment/alerts",
    operation_id="listSentimentAlertsV2",
    summary="負面情緒告警列表（tenant-scoped v2；cursor 分頁；FR-0018 / CR-0003 P2-W2）",
    response_model=SentimentAlertPage,
    tags=["Sentiment Alerts"],
)
async def list_sentiment_alerts_v2(
    tenantId: str = Path(...),
    status: SentimentAlertStatus | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await sentiment_service.list_alerts(
        tenant_id=tenantId,
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
    "/tenants/{tenantId}/sentiment/alerts/{id}",
    operation_id="updateSentimentAlertV2",
    summary="處理情緒告警（tenant-scoped v2；pending→acknowledged→resolved；FR-0018）",
    response_model=SentimentAlert,
    tags=["Sentiment Alerts"],
)
async def update_sentiment_alert_v2(
    payload: SentimentAlertUpdateRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    alert = await sentiment_service.update_alert(
        tenant_id=tenantId,
        alert_id=id,
        status=payload.status.value,
        admin_note=payload.admin_note,
    )
    body = SentimentAlert(**alert).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, body)
    return body
