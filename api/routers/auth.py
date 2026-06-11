"""Auth router — 5 endpoints (loginAdmin, loginTechnician, refreshToken, logout, registerTechnician)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, get_current_user, role_required
from core.idempotency import idempotency_guard, IdempotencyContext
from services import auth_service

logger = logging.getLogger("api.routers.auth")
router = APIRouter()


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RefreshBody(BaseModel):
    refresh_token: str


class LogoutBody(BaseModel):
    refresh_token: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class AdminResetPasswordBody(BaseModel):
    email: EmailStr


class TechnicianRegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限
    capabilities: list[str] | None = None
    regions: list[str] | None = None


@router.post(
    "/auth/login",
    operation_id="loginAdmin",
    summary="管理員登入",
    status_code=200,
)
async def login_admin(body: LoginBody) -> dict:
    return await auth_service.login(
        email=body.email, password=body.password, allowed_roles=["admin", "reviewer"]
    )


@router.post(
    "/technicians/login",
    operation_id="loginTechnician",
    summary="技師登入",
    status_code=200,
)
async def login_technician(body: LoginBody) -> dict:
    return await auth_service.login(
        email=body.email, password=body.password, allowed_roles=["technician"]
    )


@router.post(
    "/auth/refresh",
    operation_id="refreshToken",
    summary="換發 access token",
    status_code=200,
)
async def refresh_token(body: RefreshBody) -> dict:
    return await auth_service.refresh(body.refresh_token)


@router.post(
    "/auth/logout",
    operation_id="logout",
    summary="登出",
    status_code=204,
)
async def logout(
    body: LogoutBody | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.logout(
        access_jti=user.jti,
        access_user_id=user.user_id,
        access_exp_iso=None,
        refresh_token=(body.refresh_token if body else None),
    )
    return Response(status_code=204)


@router.post(
    "/auth/change-password",
    operation_id="changePassword",
    summary="變更密碼（需要當前密碼驗證）",
    status_code=204,
)
async def change_password(
    body: ChangePasswordBody,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.change_password(
        user_id=user.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return Response(status_code=204)


@router.post(
    "/auth/admin-reset-password",
    operation_id="adminResetPassword",
    summary="管理員代為重設使用者密碼（回傳臨時密碼,免 email）",
    status_code=200,
)
async def admin_reset_password(
    body: AdminResetPasswordBody,
    user: CurrentUser = Depends(role_required("admin")),
) -> dict:
    """admin 限定：重設同租戶使用者密碼為臨時密碼,回傳明文供轉達。

    機制由 2026-06-10 會議裁決（Action #7）：免 email 基礎設施。tenant_id 取自
    已認證 admin（role_required 已綁 require_tenant）,service 層限同租戶。
    """
    temp = await auth_service.admin_reset_password(
        email=body.email, tenant_id=user.tenant_id
    )
    return {"data": {"email": body.email, "temp_password": temp}}


@router.post(
    "/technicians/register",
    operation_id="registerTechnician",
    summary="技師註冊",
    status_code=201,
)
async def register_technician(
    request: Request,
    body: TechnicianRegisterBody,
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    payload = await auth_service.register_technician(body.model_dump())
    if idem is not None:
        await idem.save(201, payload)
    return payload
