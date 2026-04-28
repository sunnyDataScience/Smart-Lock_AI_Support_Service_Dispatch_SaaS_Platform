"""Technicians router — 3 endpoints (me read/patch + availability)。

operationId 對齊 openapi.yaml：
  getMyProfile, updateMyProfile, getTechnicianAvailability

只允許登入技師讀寫自己的 profile；availability 為當日 09:00–18:00 每小時 slot 的
read-only 估算（撞期工單標 hard_conflict）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, role_required
from models.generated import (
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
