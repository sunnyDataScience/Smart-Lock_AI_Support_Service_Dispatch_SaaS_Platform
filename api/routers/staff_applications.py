"""品牌員工帳號申請 router(CR-0114 R5)。

全部 tenant-scoped(對齊 v2 慣例,無 /api/v1 前綴):
- POST /tenants/{tid}/staff-applications                  公開(品牌登入頁員工申請)
- GET  /tenants/{tid}/staff-applications                  品牌 Admin 看待審
- POST /tenants/{tid}/staff-applications/{id}:approve     核准+指派角色
- POST /tenants/{tid}/staff-applications/{id}:reject      拒絕

submit 為公開端點(登入頁,無需登入):tenantId 取自 path(該品牌部署天然決定
租戶),寫進對應品牌員工池;審核走 FULL_ACCESS_ROLES(品牌 Admin,對齊 /staff)。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, EmailStr, Field

from core.deps import FULL_ACCESS_ROLES, CurrentUser, role_required
from core.errors import ApiError
from services import staff_application_service

logger = logging.getLogger("api.routers.staff_applications")
router = APIRouter()


class StaffApplicationBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=8, max_length=72)


class ApproveBody(BaseModel):
    role: str = Field(description="指派角色(∈ 5 員工角色)")


class RejectBody(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


@router.post(
    "/tenants/{tenantId}/staff-applications",
    operation_id="submitStaffApplication",
    summary="品牌員工帳號申請(公開,登入頁)",
    status_code=201,
)
async def submit_staff_application(
    body: StaffApplicationBody,
    tenantId: str = Path(...),
) -> dict:
    # 公開端點(登入頁,無需登入):tenantId 取自 path(品牌部署天然決定租戶)
    return await staff_application_service.submit(
        tenant_id=tenantId, name=body.name, email=body.email,
        phone=body.phone, password=body.password,
    )


@router.get(
    "/tenants/{tenantId}/staff-applications",
    operation_id="listStaffApplications",
    summary="品牌員工申請列表",
    status_code=200,
)
async def list_staff_applications(
    tenantId: str = Path(...),
    status: str | None = None,
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await staff_application_service.list_applications(tenant_id=tenantId, status=status)


@router.post(
    "/tenants/{tenantId}/staff-applications/{applicationId}:approve",
    operation_id="approveStaffApplication",
    summary="核准員工申請並指派角色",
    status_code=200,
)
async def approve_staff_application(
    applicationId: str,
    body: ApproveBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return await staff_application_service.approve(
        tenant_id=tenantId, app_id=applicationId, reviewer_id=user.user_id, role=body.role,
    )


@router.post(
    "/tenants/{tenantId}/staff-applications/{applicationId}:reject",
    operation_id="rejectStaffApplication",
    summary="拒絕員工申請",
    status_code=200,
)
async def reject_staff_application(
    applicationId: str,
    body: RejectBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return await staff_application_service.reject(
        tenant_id=tenantId, app_id=applicationId, reviewer_id=user.user_id, reason=body.reason,
    )
