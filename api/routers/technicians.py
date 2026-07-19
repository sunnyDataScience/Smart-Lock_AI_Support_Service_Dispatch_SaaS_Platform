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

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import CurrentUser, DISPATCH_ROLES, role_required
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
from services import technician_commission_service, technician_service

router = APIRouter()

_technician_only = role_required("technician")


# ⚠️ 路由順序：/technicians/me/* 必須註冊在 /technicians/{technician_id}/* 之前，
# 否則 {technician_id} 會以 "me" 命中 → uuid cast 失敗 500（CR-0088 踩過此雷）。
@router.get(
    "/technicians/me/dashboard-summary",
    operation_id="getMyDashboardSummary",
    summary="技師決策屏聚合（今日/本週收入、本月毛額、完成率、到場時間、客戶評價；CR-0088）",
)
async def my_dashboard_summary(user: CurrentUser = Depends(_technician_only)) -> dict:
    data = await technician_service.get_my_dashboard_summary(
        tenant_id=user.tenant_id, user_id=user.user_id,
    )
    return {"data": data}


@router.get(
    "/technicians/me/workload-heatmap",
    operation_id="getMyWorkloadHeatmap",
    summary="技師自助 workload heatmap（self-scoped，修 A37 端點 IDOR；CR-0088）",
)
async def my_workload_heatmap(
    days: int = Query(default=30, ge=1, le=90),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    data = await technician_service.get_my_workload_heatmap(
        tenant_id=user.tenant_id, user_id=user.user_id, days=days,
    )
    return {"data": data}


@router.get(
    "/technicians/{technician_id}/workload-heatmap",
    operation_id="getTechnicianWorkloadHeatmap",
    summary="取技師近 N 日 workload heatmap（A37 候選詳情 drawer）",
    response_model=dict,
)
async def get_workload_heatmap(
    technician_id: str = Path(...),
    days: int = Query(default=30, ge=1, le=90),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    """A37 排班熱力圖端點 — admin 看候選技師近 30 日 daily workload + load_intensity 分級。

    CR/0719 UAT C-7：原守衛 require_tenant 無 role 檢查 → 任何技師 token 可讀同儕
    workload（IDOR）。改 DISPATCH_ROLES（admin/ops/dispatcher 派工方管理視角）。
    """
    data = await technician_service.get_technician_workload_heatmap(
        tenant_id=user.tenant_id,
        technician_id=technician_id,
        days=days,
    )
    return {"data": data}


@router.get(
    "/technicians/me",
    operation_id="getMyTechnicianProfile",
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
    operation_id="updateMyTechnicianProfile",
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
    "/technicians/me/commission-statements",
    operation_id="listMyCommissionStatements",
    summary="技師本人佣金對帳單（月彙總；UAT P2-5 補端點，讀 R4 佣金投影）",
)
async def list_my_commission_statements(
    limit: int = Query(default=24, ge=1, le=60, description="最多回傳期數（月）"),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    data = await technician_commission_service.list_my_commission_statements(
        tenant_id=user.tenant_id, user_id=user.user_id, limit=limit,
    )
    return {"data": data}


@router.get(
    "/technicians",
    operation_id="listTechnicians",
    summary="技師列表（管理員視角，cursor 分頁）[DEPRECATED — 請遷移至 /tenants/{tenantId}/technicians]",
    response_model=TechnicianPage,
)
async def list_technicians(
    response: Response,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    availability: TechnicianAvailability | None = Query(default=None),
    level: TechnicianLevel | None = Query(default=None),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    # CR/0719 UAT C-7：原 require_tenant 無 role 檢查 → 技師 token 可枚舉全租戶
    # 技師名冊 PII（phone/service_areas/rating）。此為「管理員視角」端點，改
    # DISPATCH_ROLES 擋 technician/其他角色（admin/ops/dispatcher 才可管理技師）。
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        f"</tenants/{user.tenant_id}/technicians>; rel=\"successor-version\""
    )
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
    summary="技師詳情（管理員視角）[DEPRECATED — 請遷移至 /tenants/{tenantId}/technicians/{techId}]",
    response_model=TechnicianEnvelope,
)
async def get_technician(
    response: Response,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    # CR/0719 UAT C-7：同 list_technicians，管理員視角詳情改 DISPATCH_ROLES。
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        f"</tenants/{user.tenant_id}/technicians/{id}>; rel=\"successor-version\""
    )
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
