"""X-Tenant-ID header 解析與驗證。

login/refresh/register 端點不檢查 tenant（因為還沒登入）；其他端點：
- 必須帶 header
- 必須與 JWT claim 中的 tenant_id 相符
"""

from __future__ import annotations

from fastapi import Header

from core.errors import ApiError


async def resolve_tenant_id(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    if not x_tenant_id:
        raise ApiError(
            error_code="MISSING_TENANT",
            message="X-Tenant-ID header is required",
            status_code=400,
        )
    return x_tenant_id


async def resolve_optional_tenant_id(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str | None:
    return x_tenant_id
