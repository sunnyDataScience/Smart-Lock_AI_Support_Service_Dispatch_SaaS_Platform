"""Auth router — 5 endpoints (loginAdmin, loginTechnician, refreshToken, logout, registerTechnician)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, get_current_user, role_required
from core.idempotency import idempotency_guard, IdempotencyContext
from services import auth_service, password_reset_service

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


class RequestPasswordResetBody(BaseModel):
    email: EmailStr


class ConfirmPasswordResetBody(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限


class TechnicianRegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限
    capabilities: list[str] | None = None
    regions: list[str] | None = None


# admin web 可登入的後台角色（CR-0021 Q2）。technician 走 /technicians/login。
# 放寬只是讓這些後台角色能取得 admin-web token;各 endpoint 仍受後端 role_required 守衛。
_ADMIN_WEB_ROLES = [
    "admin",
    "reviewer",
    "operations_manager",
    "dispatcher",
    "customer_service",
]


@router.post(
    "/auth/login",
    operation_id="loginAdmin",
    summary="管理員登入",
    status_code=200,
)
async def login_admin(body: LoginBody) -> dict:
    return await auth_service.login(
        email=body.email, password=body.password, allowed_roles=_ADMIN_WEB_ROLES
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
    "/auth/request-password-reset",
    operation_id="requestPasswordReset",
    summary="申請密碼重設（自助，寄送重設連結到 email）",
    status_code=200,
)
async def request_password_reset(body: RequestPasswordResetBody, request: Request) -> dict:
    """自助忘記密碼 step 1（CR-0025 / ADR-0114）。

    **帳號枚舉防護**：不論 email 是否存在，一律回 200 同一訊息；實際是否寄出由
    service 端決定（不存在 / 停用 / rate-limit / SMTP 未配置皆安靜略過）。
    """
    client_ip = request.client.host if request.client else None
    await password_reset_service.request_reset(email=body.email, request_ip=client_ip)
    return {"data": None, "message": "若該帳號存在，重設連結已寄出，請於 30 分鐘內使用"}


@router.post(
    "/auth/confirm-password-reset",
    operation_id="confirmPasswordReset",
    summary="以重設 token 設定新密碼",
    status_code=204,
)
async def confirm_password_reset(body: ConfirmPasswordResetBody) -> Response:
    """自助忘記密碼 step 2：驗 token（未過期/未用）→ 設新密碼 → 標 token 已用。"""
    await password_reset_service.confirm_reset(token=body.token, new_password=body.new_password)
    return Response(status_code=204)


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


class VendorRegisterBody(BaseModel):
    """發案者（品牌商/鎖店/經銷商）註冊（CR-0029）。"""

    vendor_type: str = Field(description="brand/locksmith/distributor")
    name: str = Field(min_length=1, max_length=150)
    company_name: str = Field(min_length=1, max_length=150)  # CR-0089 改必填（發案者為公司）
    tax_id: str = Field(pattern=r"^\d{8}$", description="統一編號 8 碼")  # CR-0089 新增（B2B 開發票）
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限
    address: str | None = Field(default=None, max_length=300)


@router.post(
    "/vendors/register",
    operation_id="registerVendor",
    summary="廠商/品牌商註冊（發案者，CR-0029）",
    status_code=201,
)
async def register_vendor(
    request: Request,
    body: VendorRegisterBody,
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    payload = await auth_service.register_vendor(body.model_dump())
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.post(
    "/vendors/login",
    operation_id="loginVendor",
    summary="廠商/品牌商登入（發案者，CR-0029；與後台角色隔離）",
    status_code=200,
)
async def login_vendor(body: LoginBody) -> dict:
    return await auth_service.login(
        email=body.email, password=body.password, allowed_roles=["vendor"]
    )
