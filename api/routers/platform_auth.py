"""Platform console auth router（CR-0114）— login / refresh / logout / me。

全部收在 /api/v1/platform 前綴下(API_SURFACE=platform 以單一前綴過濾,
見 api/main.py _PLATFORM_SURFACE_PREFIXES)。守衛 = require_platform_admin
(非 tenant-scoped,不收 X-Tenant-ID)。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, get_current_user, require_platform_admin
from core.errors import ApiError
from services import platform_admin_service

logger = logging.getLogger("api.routers.platform_auth")
router = APIRouter()


class PlatformLoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class PlatformRefreshBody(BaseModel):
    refresh_token: str


class PlatformLogoutBody(BaseModel):
    refresh_token: str | None = None


@router.post(
    "/platform/auth/login",
    operation_id="loginPlatformAdmin",
    summary="平台管理員登入",
    status_code=200,
)
async def login_platform_admin(body: PlatformLoginBody) -> dict:
    return await platform_admin_service.login(body.email, body.password)


@router.post(
    "/platform/auth/refresh",
    operation_id="refreshPlatformToken",
    summary="平台 token 換發",
    status_code=200,
)
async def refresh_platform_token(body: PlatformRefreshBody) -> dict:
    return await platform_admin_service.refresh(body.refresh_token)


@router.post(
    "/platform/auth/logout",
    operation_id="logoutPlatformAdmin",
    summary="平台管理員登出",
    status_code=204,
)
async def logout_platform_admin(
    body: PlatformLogoutBody | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    # 用 get_current_user 而非 require_platform_admin:登出只需有效 token,
    # 但撤銷一律寫平台庫 → 非平台 token 直接拒絕,避免污染品牌 revoked_jti。
    if user.role != "platform_admin":
        raise ApiError("FORBIDDEN", "Platform admin role required", 403)
    await platform_admin_service.logout(
        access_jti=user.jti,
        access_user_id=user.user_id,
        refresh_token=(body.refresh_token if body else None),
    )
    return Response(status_code=204)


@router.get(
    "/platform/me",
    operation_id="getPlatformMe",
    summary="目前平台管理員",
    status_code=200,
)
async def get_platform_me(
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await platform_admin_service.me(user.user_id)
