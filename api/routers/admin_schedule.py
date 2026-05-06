"""Admin 端：技師排班申請審核 router。

operationId 對齊 openapi.yaml：
  - listScheduleRequests   (GET  /admin/schedule-requests)
  - approveScheduleRequest (POST /admin/schedule-requests/{id}/approve)
  - rejectScheduleRequest  (POST /admin/schedule-requests/{id}/reject)

權限：admin / operations_manager（排班屬人事權限，限管理層）。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, role_required
from services import technician_schedule_service

router = APIRouter()

_admin_only = role_required("admin", "operations_manager")


class _ResolveRequestBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get(
    "/admin/schedule-requests",
    operation_id="listScheduleRequests",
    summary="列出 tenant 內所有排班申請（可依 status / type 過濾）",
)
async def list_schedule_requests(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(
        default=None
    ),
    type: Literal["leave", "standby"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(_admin_only),
) -> dict:
    return await technician_schedule_service.list_schedule_requests(
        tenant_id=user.tenant_id,
        status=status,
        type_filter=type,
        limit=limit,
    )


@router.post(
    "/admin/schedule-requests/{request_id}/approve",
    operation_id="approveScheduleRequest",
    summary="核准排班申請（pending → approved）",
)
async def approve_schedule_request(
    body: _ResolveRequestBody | None = None,
    request_id: str = Path(),
    user: CurrentUser = Depends(_admin_only),
) -> dict:
    return await technician_schedule_service.resolve_schedule_request(
        tenant_id=user.tenant_id,
        resolver_user_id=user.user_id,
        request_id=request_id,
        decision="approved",
        note=body.note if body else None,
    )


@router.post(
    "/admin/schedule-requests/{request_id}/reject",
    operation_id="rejectScheduleRequest",
    summary="拒絕排班申請（pending → rejected）",
)
async def reject_schedule_request(
    body: _ResolveRequestBody | None = None,
    request_id: str = Path(),
    user: CurrentUser = Depends(_admin_only),
) -> dict:
    return await technician_schedule_service.resolve_schedule_request(
        tenant_id=user.tenant_id,
        resolver_user_id=user.user_id,
        request_id=request_id,
        decision="rejected",
        note=body.note if body else None,
    )
