"""Auth router — 5 endpoints (loginAdmin, loginTechnician, refreshToken, logout, registerTechnician)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, get_current_user
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
