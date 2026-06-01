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


@dataclass
class SodActors:
    """SoD 三維行為人（BR-M17-01 / ADR-0102 §D）。"""

    initiator: str
    approver: str
    executor: str | None


async def require_sod_actors(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
    x_executor: str | None = Header(default=None, alias="X-Executor"),
) -> SodActors:
    """解析 X-Initiator / X-Approver / X-Executor headers。

    spec（openapi-smart-lock-saas.yaml）: X-Initiator + X-Approver required，
    X-Executor optional。任二相同 → 403 SOD_VIOLATION。
    """
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    if not x_approver:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Approver", 422)
    actors = [a for a in (x_initiator, x_approver, x_executor) if a]
    if len(actors) != len(set(actors)):
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: X-Initiator / X-Approver / X-Executor must be distinct",
            403,
        )
    return SodActors(initiator=x_initiator, approver=x_approver, executor=x_executor)


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
