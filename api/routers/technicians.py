"""Technicians router — 5 endpoints。

operationId 對齊 openapi.yaml：
  - getMyProfile / updateMyProfile / getTechnicianAvailability（登入技師自身）
  - listTechnicians（管理員：tenant 內 cursor 分頁）
  - getTechnician（管理員：單筆查詢）

只允許登入技師讀寫自己的 profile；admin list/get 僅需 tenant 隔離。availability
為當日 09:00–18:00 每小時 slot 的 read-only 估算（撞期工單標 hard_conflict）。

路由順序：me / me/availability 必須在 {id} 之前，否則 FastAPI 會以 id="me" 命中。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant, role_required
from models.generated import (
    Technician,
    TechnicianAvailability,
    TechnicianEnvelope,
    TechnicianLevel,
    TechnicianPage,
    TechnicianProfile,
    TechnicianProfileEnvelope,
    TechnicianUpdateRequest,
)
from services import technician_service

router = APIRouter()

_technician_only = role_required("technician")


@router.get(
    "/technicians/me",
    operation_id="getMyProfile",
    summary="取得目前登入技師個人資料",
    response_model=TechnicianProfileEnvelope,
)
async def get_my_profile(user: CurrentUser = Depends(_technician_only)) -> dict:
    profile = await technician_service.get_my_profile(
        tenant_id=user.tenant_id, user_id=user.user_id,
    )
    return {"data": TechnicianProfile(**profile).model_dump(mode="json")}


@router.patch(
    "/technicians/me",
    operation_id="updateMyProfile",
    summary="更新個人資料",
    response_model=TechnicianProfileEnvelope,
)
async def update_my_profile(
    body: TechnicianUpdateRequest,
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    patch = body.model_dump(exclude_unset=True)
    profile = await technician_service.update_my_profile(
        tenant_id=user.tenant_id, user_id=user.user_id, patch=patch,
    )
    return {"data": TechnicianProfile(**profile).model_dump(mode="json")}


@router.get(
    "/technicians/me/availability",
    operation_id="getTechnicianAvailability",
    summary="查詢技師自己某日可用時段",
)
async def get_my_availability(
    date: str = Query(..., description="YYYY-MM-DD"),
    work_order_id: str | None = Query(default=None),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    return await technician_service.get_my_availability(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        date_str=date,
        work_order_id=work_order_id,
    )


@router.get(
    "/technicians",
    operation_id="listTechnicians",
    summary="技師列表（管理員視角，cursor 分頁）",
    response_model=TechnicianPage,
)
async def list_technicians(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    availability: TechnicianAvailability | None = Query(default=None),
    level: TechnicianLevel | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await technician_service.list_technicians(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        availability=availability.value if availability else None,
        level=level.value if level else None,
    )
    return {
        "items": [Technician(**t).model_dump(mode="json") for t in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/technicians/{id}",
    operation_id="getTechnician",
    summary="技師詳情（管理員視角）",
    response_model=TechnicianEnvelope,
)
async def get_technician(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    technician = await technician_service.get_technician(
        tenant_id=user.tenant_id, technician_id=id,
    )
    return {"data": Technician(**technician).model_dump(mode="json")}


# =============================================================================
# T10 排班 + PATCH availability
# =============================================================================

from typing import Literal as _Literal  # noqa: E402

from fastapi import Body  # noqa: E402
from pydantic import BaseModel as _BaseModel, Field as _Field  # noqa: E402

from services import technician_schedule_service  # noqa: E402


class _AvailabilityPatchRequest(_BaseModel):
    online_state: _Literal[
        "available", "busy", "offline", "on_leave", "circuit_breaker_open"
    ]


class _ScheduleRequestBody(_BaseModel):
    start_date: str = _Field(..., description="YYYY-MM-DD")
    end_date: str = _Field(..., description="YYYY-MM-DD")
    reason: str = _Field(..., min_length=5, max_length=500)


@router.patch(
    "/technicians/me/availability",
    operation_id="updateMyAvailability",
    summary="切換在線狀態（available / busy / offline / on_leave / circuit_breaker_open）",
)
async def update_my_availability(
    body: _AvailabilityPatchRequest,
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    result = await technician_schedule_service.update_my_online_state(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        online_state=body.online_state,
    )
    return {"data": result}


@router.get(
    "/technicians/me/schedule",
    operation_id="getMySchedule",
    summary="取得當月排班（每日工單數 + 休假/備勤標記 + 待審核申請）",
)
async def get_my_schedule(
    month: str = Query(..., description="YYYY-MM"),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    return await technician_schedule_service.get_my_schedule(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        month_str=month,
    )


@router.post(
    "/technicians/me/schedule/leave-request",
    operation_id="createLeaveRequest",
    summary="申請休假",
)
async def create_leave_request(
    body: _ScheduleRequestBody,
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    return await technician_schedule_service.create_schedule_request(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        request_type="leave",
        start_date_str=body.start_date,
        end_date_str=body.end_date,
        reason=body.reason,
    )


@router.post(
    "/technicians/me/schedule/standby-request",
    operation_id="createStandbyRequest",
    summary="申請備勤",
)
async def create_standby_request(
    body: _ScheduleRequestBody,
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    return await technician_schedule_service.create_schedule_request(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        request_type="standby",
        start_date_str=body.start_date,
        end_date_str=body.end_date,
        reason=body.reason,
    )


@router.delete(
    "/technicians/me/schedule/request/{request_id}",
    operation_id="cancelScheduleRequest",
    summary="取消待審核申請",
)
async def cancel_schedule_request(
    request_id: str = Path(),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    return await technician_schedule_service.cancel_schedule_request(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        request_id=request_id,
    )
