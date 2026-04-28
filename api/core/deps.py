"""FastAPI dependencies — 把 auth/tenant/db 注入到 router handler。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Header, Request

from core.auth import decode_token, is_jti_revoked
from core.errors import ApiError
from core.tenant import resolve_tenant_id

logger = logging.getLogger("api.deps")


@dataclass
class CurrentUser:
    user_id: str
    role: str
    tenant_id: str
    jti: str
    token_type: str


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Missing or invalid Authorization header",
            status_code=401,
        )
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token)
    except Exception:
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Invalid or expired token",
            status_code=401,
        )

    if payload.get("type") != "access":
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Refresh token cannot be used for API access",
            status_code=401,
        )

    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti):
        raise ApiError(
            error_code="TOKEN_REVOKED",
            message="Token has been revoked",
            status_code=401,
        )

    return CurrentUser(
        user_id=payload["sub"],
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id", ""),
        jti=jti or "",
        token_type=payload.get("type", "access"),
    )


async def get_current_user_with_tenant(
    user: CurrentUser = ...,  # filled at runtime via Depends chain below
) -> CurrentUser:
    """Placeholder — 實際 chain 在 require_tenant 中組合。"""
    return user


async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> CurrentUser:
    """同時驗 JWT + 比對 X-Tenant-ID 與 claim 一致。"""
    user = await get_current_user(authorization)
    tenant = await resolve_tenant_id(x_tenant_id)
    if user.tenant_id and user.tenant_id != tenant:
        raise ApiError(
            error_code="TENANT_MISMATCH",
            message="X-Tenant-ID does not match token claim",
            status_code=403,
        )
    return user


async def require_admin(user: CurrentUser) -> CurrentUser:
    if user.role != "admin":
        raise ApiError(
            error_code="FORBIDDEN",
            message="Admin role required",
            status_code=403,
        )
    return user


def role_required(*roles: str):
    """Dependency factory 限制角色。"""
    async def _dep(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> CurrentUser:
        user = await require_tenant(request, authorization, x_tenant_id)
        if roles and user.role not in roles:
            raise ApiError(
                error_code="FORBIDDEN",
                message=f"Requires one of roles: {', '.join(roles)}",
                status_code=403,
            )
        return user
    return _dep
