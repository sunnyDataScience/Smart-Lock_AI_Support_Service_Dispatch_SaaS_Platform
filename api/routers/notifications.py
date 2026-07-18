"""Notifications router — 6 endpoints。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field

from core.config import load_config
from core.deps import CurrentUser, OPS_ROLES, require_tenant, role_required
from core.idempotency import idempotency_guard, IdempotencyContext
from services import notification_service

router = APIRouter()


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


class PushBody(BaseModel):
    target_type: Literal["user", "role", "all"]
    target_id: str
    type: str
    title: str
    body: str
    data: dict | None = None
    channels: list[str] | None = None
    # UAT-0718 W5-3（已釘契約）：可點跳轉關聯，如
    # {"type":"work_order","id":"<uuid>","url":"/work-orders/<uuid>"}
    related_entity: dict | None = None


@router.get(
    "/notifications",
    operation_id="listNotifications",
    summary="通知列表",
)
async def list_notifications(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status_q: str | None = Query(default=None, alias="status"),
    types: list[str] | None = Query(default=None, alias="type"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    cfg = load_config().pagination
    effective_limit = min(limit, cfg.get("max_limit", 100))
    return await notification_service.list_notifications(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        cursor=cursor,
        limit=effective_limit,
        status=status_q,
        types=types,
    )


@router.patch(
    "/notifications/{id}",
    operation_id="updateNotification",
    summary="標記通知狀態",
)
async def update_notification(
    body: UpdateBody,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await notification_service.update_notification(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        notification_id=id,
        read_at=body.read_at,
        archived_at=body.archived_at,
    )


@router.post(
    "/notifications/bulk",
    operation_id="bulkUpdateNotifications",
    summary="批量處理通知",
)
async def bulk_update_notifications(
    body: BulkBody,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    payload = await notification_service.bulk_action(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        ids=body.ids,
        action=body.action,
    )
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/notifications/mark-all-read",
    operation_id="markAllNotificationsRead",
    summary="全部標為已讀（Critical 類除外）",
)
async def mark_all_notifications_read(
    body: MarkAllReadBody | None = None,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    type_filter = body.filter.type if body and body.filter else None
    payload = await notification_service.mark_all_read(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        type_filter=type_filter,
    )
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/notifications/push",
    operation_id="pushNotification",
    summary="主動推播通知",
    status_code=status.HTTP_202_ACCEPTED,
)
async def push_notification(
    body: PushBody,
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    payload = await notification_service.push_notification(
        body.model_dump(), tenant_id=user.tenant_id
    )
    if idem is not None:
        await idem.save(202, payload)
    return payload
