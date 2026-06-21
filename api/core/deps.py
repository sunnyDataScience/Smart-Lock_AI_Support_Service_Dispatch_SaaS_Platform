"""FastAPI dependencies — 把 auth/tenant/db 注入到 router handler。"""

from __future__ import annotations

import hmac
import logging
import os
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


# ---------------------------------------------------------------------------
# CR-0092 — 標準角色集合（單一真相源）
#
# 為什麼集中在此：稽核發現 407 端點中 80 個敏感寫入只用 require_tenant（不檢查
# 角色），任何登入者含 technician/vendor 皆可寫金流/設定/派工。各 router 原本
# 各自定義 _BILLING_ROLES / _APPROVE_ROLES / _DISPATCH_ALLOWED_ROLES，集合不一
# 且常漏掛。以下常數為「既有 gated 端點角色集的超集 + super_admin」：
#   - 不破既有存取（既有集合皆為子集，只多放行 super_admin，修正其被誤擋的潛在 bug）
#   - 對齊前端 web/src/lib/rolePolicy.ts 意圖（後台頁 admin/ops/dispatcher/cs）
# ---------------------------------------------------------------------------

#: 全權管理角色（admin governance：config / roles / audit / GDPR / data-correction）
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin", "tenant_admin", "super_admin")
#: 營運後台寫入（accounting / billing / pricing / vendor-mgmt / warranty / 結算）
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
#: 派工寫入（dispatch / 自動媒合 / 技師生命週期管理）
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
#: 後台唯讀／一般後台操作（含客服）
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)


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


# HD-VCH-003：platform keeper role — X-Keeper-Role header + user.role 屬平台管理員集合
_KEEPER_ROLES: frozenset[str] = frozenset({"admin", "platform_admin", "platform_keeper"})


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """服務間（service-to-service）internal token 驗證。

    用於非人類發動、無 JWT 的內部寫入路徑（如 LINE agent gateway 把對話旁路
    持久化到 conversations/messages，方案 A）。期望 token 來自環境變數
    `INTERNAL_API_TOKEN`。

    **Fail closed**：env 未設定時一律拒絕（503），絕不放行無認證的 DB 寫入端點。
    比對用 `hmac.compare_digest` 做常數時間比較，避免 timing attack。
    """
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 留 \n）；
    # 兩邊都 strip 才能正確比對（agent 端送 header 前亦 strip）。
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        raise ApiError(
            error_code="INTERNAL_AUTH_NOT_CONFIGURED",
            message="Internal API token not configured on server",
            status_code=503,
        )
    incoming = (x_internal_token or "").strip()
    if not incoming or not hmac.compare_digest(incoming, expected):
        raise ApiError(
            error_code="INTERNAL_AUTH_FAILED",
            message="Missing or invalid X-Internal-Token",
            status_code=401,
        )


async def require_keeper_role(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_keeper_role: str | None = Header(default=None, alias="X-Keeper-Role"),
) -> CurrentUser:
    """Voucher void 專用 dependency（HD-VCH-003）。

    檢查：
      1. Bearer token 有效（get_current_user）
      2. X-Keeper-Role header 必填
      3. user.role 屬 platform admin 集合（_KEEPER_ROLES）

    flat path（/vouchers/{id}/void）不做 tenant 綁定；keeper 可跨租戶操作，
    voucher 自帶 tenant_id 做隔離。
    """
    user = await get_current_user(authorization)
    if not x_keeper_role:
        raise ApiError(
            error_code="KEEPER_ROLE_REQUIRED",
            message="Missing X-Keeper-Role header",
            status_code=403,
        )
    if user.role not in _KEEPER_ROLES:
        raise ApiError(
            error_code="KEEPER_FORBIDDEN",
            message="Voucher void requires platform keeper role",
            status_code=403,
        )
    return user
