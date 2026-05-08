"""F-010 Reschedule / Delay quick-action endpoints (with real LINE Push).

Endpoints
---------
- POST /work-orders/{id}/reschedule-request   → requestReschedule (technician/admin)
- POST /work-orders/{id}/reschedule/approve   → approveReschedule (admin/ops_manager)
- POST /work-orders/{id}/notify-delay         → notifyDelay (technician/admin)

These complement the existing flow ops:
- proposeReschedule → LINE Flex RSVP (Flow 11, 24h TTL)
- recordDelay       → 純事件記錄（不推送）

對齊 PM Q8=A V1.0：only LINE 拒收非 LINE 用戶 → notification_sent=false（不報錯）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from core.deps import CurrentUser, role_required
from services import work_order_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class _RequestRescheduleBody(BaseModel):
    new_scheduled_at: datetime = Field(..., description="ISO 8601 future datetime")
    reason: str = Field(..., min_length=1, max_length=500)


class _ApproveRescheduleBody(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


class _NotifyDelayBody(BaseModel):
    delay_minutes: int = Field(..., ge=5, le=300)
    reason: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------


# 技師可改自己的工單；admin / operations_manager 可改任何工單（service 層做 ownership 檢查）
_tech_or_admin = role_required("technician", "admin", "operations_manager", "tenant_admin")
_admin_only = role_required("admin", "operations_manager", "tenant_admin")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/work-orders/{id}/reschedule-request",
    operation_id="requestReschedule",
    summary="技師 / 管理員直接改約（單方變更，附 LINE 通知）",
)
async def request_reschedule(
    body: _RequestRescheduleBody,
    id: str = Path(),
    user: CurrentUser = Depends(_tech_or_admin),
) -> dict:
    result = await work_order_service.request_reschedule(
        tenant_id=user.tenant_id,
        wo_id=id,
        new_scheduled_at=body.new_scheduled_at.isoformat(),
        reason=body.reason,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return result


@router.post(
    "/work-orders/{id}/reschedule/approve",
    operation_id="approveReschedule",
    summary="管理員核准 / 退回改約申請",
)
async def approve_reschedule(
    body: _ApproveRescheduleBody,
    id: str = Path(),
    user: CurrentUser = Depends(_admin_only),
) -> dict:
    result = await work_order_service.approve_reschedule(
        tenant_id=user.tenant_id,
        wo_id=id,
        decision=body.decision,
        comment=body.comment,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return result


@router.post(
    "/work-orders/{id}/notify-delay",
    operation_id="notifyDelay",
    summary="技師現場延遲，主動 LINE 通知客戶",
)
async def notify_delay(
    body: _NotifyDelayBody,
    id: str = Path(),
    user: CurrentUser = Depends(_tech_or_admin),
) -> dict:
    result = await work_order_service.notify_delay(
        tenant_id=user.tenant_id,
        wo_id=id,
        delay_minutes=body.delay_minutes,
        reason=body.reason,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return result
