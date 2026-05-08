"""Roles router — 角色與權限矩陣 + F-019 動態調整。

operationId 對齊 openapi.yaml：
  - listRoles               — 5 系統角色 + 各角色於本租戶的使用者數 + 權限矩陣
  - updateRolePermissions   — F-019 動態調整角色權限（含 Director > Manager 階層強制
                              + WS publish + audit log）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from models.generated import Role, RolesEnvelope
from services import role_service

logger = logging.getLogger("api.roles_router")

router = APIRouter()


@router.get(
    "/roles",
    operation_id="listRoles",
    summary="角色與權限矩陣（含動態 overrides；本租戶各角色使用者數）",
    response_model=RolesEnvelope,
)
async def list_roles(user: CurrentUser = Depends(require_tenant)) -> dict:
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
    summary="動態調整角色權限（admin / tenant_admin / super_admin；強制階層）",
)
async def update_role_permissions(
    role_name: str = Path(..., description="角色 ID"),
    body: _UpdateRolePermissionsBody = Body(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """PATCH /api/v1/roles/{role_name}/permissions"""
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
