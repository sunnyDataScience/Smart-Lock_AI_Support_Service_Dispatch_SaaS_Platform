"""Roles router — 角色與權限矩陣 + F-019 動態調整。

operationId 對齊 openapi.yaml：
  - listRoles               — 5 系統角色 + 各角色於本租戶的使用者數 + 權限矩陣
  - updateRolePermissions   — F-019 動態調整角色權限（含 Director > Manager 階層強制
                              + WS publish + audit log）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import BaseModel, Field

from core.deps import FULL_ACCESS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import Role, RolesEnvelope
from services import auth_service, role_service

# D3：legacy 端點 Deprecation header 常數（successor 為 tenant-scoped v2 路徑）
_DEPRECATION_HEADER = "true"
_SUCCESSOR_LINK_ROLES = '</tenants/{tid}/rbac/roles>; rel="successor-version"'
_SUCCESSOR_LINK_PERMS = '</tenants/{tid}/rbac/roles/{role}/permissions>; rel="successor-version"'

logger = logging.getLogger("api.roles_router")

router = APIRouter()


@router.get(
    "/roles",
    operation_id="listRoles",
    summary="角色與權限矩陣（含動態 overrides；本租戶各角色使用者數）[DEPRECATED → v2]",
    response_model=RolesEnvelope,
)
async def list_roles(
    response: Response,
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    # D3：標示此端點已棄用，後繼為 tenant-scoped v2
    tid = user.tenant_id or "{tenantId}"
    response.headers["Deprecation"] = _DEPRECATION_HEADER
    response.headers["Link"] = _SUCCESSOR_LINK_ROLES.format(tid=tid)
    roles = await role_service.list_roles(tenant_id=user.tenant_id)
    return {"data": [Role(**r).model_dump(mode="json") for r in roles]}


# ─── F-019：updateRolePermissions ────────────────────────────────


class _UpdateRolePermissionsBody(BaseModel):
    """對齊 OpenAPI RolePermissionsUpdateRequest。"""

    permissions: list[str] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="扁平化權限碼清單（resource.action）",
    )
    reason: str = Field(..., min_length=4, max_length=500)


@router.patch(
    "/roles/{role_name}/permissions",
    operation_id="updateRolePermissions",
    summary="動態調整角色權限（admin / tenant_admin / super_admin；強制階層）[DEPRECATED → v2]",
)
async def update_role_permissions(
    response: Response,
    role_name: str = Path(..., description="角色 ID"),
    body: _UpdateRolePermissionsBody = Body(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """PATCH /api/v1/roles/{role_name}/permissions — [DEPRECATED: 遷移至 PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions]"""
    # D3：標示此端點已棄用
    tid = user.tenant_id or "{tenantId}"
    response.headers["Deprecation"] = _DEPRECATION_HEADER
    response.headers["Link"] = _SUCCESSOR_LINK_PERMS.format(tid=tid, role=role_name)
    # 階層 / 越權檢查在 service 層；這裡只做 thin handler
    try:
        result = await role_service.update_role_permissions(
            tenant_id=user.tenant_id,
            role_name=role_name,
            desired_permissions=list(body.permissions),
            actor_id=user.user_id,
            actor_role=user.role,
            reason=body.reason,
        )
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("updateRolePermissions failed")
        raise ApiError(
            "INTERNAL_ERROR",
            f"role permissions update failed: {exc}",
            500,
        ) from exc

    return {"data": result}


# ─── CR-0094：後台員工帳號建立（解「5 角色只有 admin」）────────────


class _CreateStaffBody(BaseModel):
    """建立後台員工帳號（admin 專用）。role 限 _STAFF_ROLES（service 驗證）。"""

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(..., description="operations_manager / dispatcher / customer_service / reviewer / admin")
    phone: str | None = Field(default=None, max_length=50)


@router.get(
    "/staff",
    operation_id="listStaff",
    summary="列出後台員工帳號（admin / tenant_admin / super_admin）",
)
async def list_staff(
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    return await auth_service.list_staff_users(tenant_id=user.tenant_id)


@router.post(
    "/staff",
    operation_id="createStaff",
    summary="建立後台員工帳號（admin / tenant_admin / super_admin）",
    status_code=201,
)
async def create_staff(
    body: _CreateStaffBody,
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    return await auth_service.create_staff_user(
        body.model_dump(), tenant_id=user.tenant_id
    )
