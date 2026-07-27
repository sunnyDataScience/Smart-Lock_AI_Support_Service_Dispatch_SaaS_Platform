"""Notifications v2 — tenant-scoped（CR-0003 P2-W2 / ADR-0012 / FR-0018）。

spec 對齊（路徑全部無 /api/v1 前綴，frozen spec 定義）：
  GET  /tenants/{tenantId}/notifications
       → listNotifications（游標分頁，status/type 過濾）
  PATCH /tenants/{tenantId}/notifications/{notificationId}
       → updateNotification（標記已讀 / 封存）
  POST  /tenants/{tenantId}/notifications:bulk
       → bulkUpdateNotifications（批次 mark_read/mark_unread/archive/delete）
  POST  /tenants/{tenantId}/notifications:mark-all-read
       → markAllNotificationsRead（Critical 類除外）

push（POST /api/v1/notifications/push）= 平台級操作，語意不屬 tenant-scoped 查詢；
保留 legacy 路徑，此處不重覆對映。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard 套用 POST 寫操作（W1 教訓）
  - 呼既有 notification_service；零重寫業務邏輯
  - 回傳型別：dict（寬鬆 envelope，避免 float/None/pattern mismatch；W1 教訓）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.config import load_config
from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import notification_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------


class UpdateBody(BaseModel):
    read_at: datetime | None = None
    archived_at: datetime | None = None


class BulkBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=1000)
    action: Literal["mark_read", "mark_unread", "archive", "delete"]


class MarkAllReadFilter(BaseModel):
    type: list[str] | None = None


class MarkAllReadBody(BaseModel):
    filter: MarkAllReadFilter | None = None


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/notifications
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/notifications",
    operation_id="listNotificationsV2",
    summary="通知列表 v2（tenant-scoped，游標分頁，status/type 過濾）",
    tags=["Notifications"],
)
async def list_notifications_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status_q: str | None = Query(default=None, alias="status"),
    types: list[str] | None = Query(default=None, alias="type"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    cfg = load_config().pagination
    effective_limit = min(limit, cfg.get("max_limit", 100))

    return await notification_service.list_notifications(
        tenant_id=tenantId,
        user_id=user.user_id,
        cursor=cursor,
        limit=effective_limit,
        status=status_q,
        types=types,
    )


# ---------------------------------------------------------------------------
# PATCH /tenants/{tenantId}/notifications/{notificationId}
# ---------------------------------------------------------------------------


@router.patch(
    "/tenants/{tenantId}/notifications/{notificationId}",
    operation_id="updateNotificationV2",
    summary="標記通知狀態 v2（tenant-scoped，標記已讀或封存）",
    tags=["Notifications"],
)
async def update_notification_v2(
    body: UpdateBody,
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    notificationId: str = Path(..., description="通知 UUID"),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    payload = await notification_service.update_notification(
        tenant_id=tenantId,
        user_id=user.user_id,
        notification_id=notificationId,
        read_at=body.read_at,
        archived_at=body.archived_at,
    )
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/notifications:bulk
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/notifications:bulk",
    operation_id="bulkUpdateNotificationsV2",
    summary="批次處理通知 v2（tenant-scoped，mark_read/mark_unread/archive/delete）",
    tags=["Notifications"],
)
async def bulk_update_notifications_v2(
    body: BulkBody,
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    payload = await notification_service.bulk_action(
        tenant_id=tenantId,
        user_id=user.user_id,
        ids=body.ids,
        action=body.action,
    )

    if idem is not None:
        await idem.save(200, payload)

    return payload


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/notifications:mark-all-read
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/notifications:mark-all-read",
    operation_id="markAllNotificationsReadV2",
    summary="全部標為已讀 v2（tenant-scoped，Critical 類除外）",
    tags=["Notifications"],
)
async def mark_all_notifications_read_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    body: MarkAllReadBody | None = None,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    type_filter = body.filter.type if body and body.filter else None

    payload = await notification_service.mark_all_read(
        tenant_id=tenantId,
        user_id=user.user_id,
        type_filter=type_filter,
    )

    if idem is not None:
        await idem.save(200, payload)

    return payload
