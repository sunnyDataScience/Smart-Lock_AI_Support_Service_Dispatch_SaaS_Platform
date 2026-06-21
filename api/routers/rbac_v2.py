"""RBAC v2 router — tenant-scoped 角色端點（CR-0002-α / spec §2.2 gap fill）。

雙掛過渡策略（ADR 對齊 refunds_v2 / cancellation 先例）：
  - v2 路徑：GET  /tenants/{tenantId}/rbac/roles
             PUT  /tenants/{tenantId}/rbac/roles/{roleName}/permissions
  - legacy  /api/v1/roles（GET）+ /api/v1/roles/{role}/permissions（PATCH）
    保留且加 Deprecation header（D3），前端遷移後於後續波次移除。

v2 呼叫既有 role_service 函式，不重寫業務邏輯：
  - list_roles(tenant_id)
  - update_role_permissions(tenant_id, role_name, desired_permissions, actor_id, actor_role, reason)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel, Field

from core.deps import FULL_ACCESS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import Role, RolesEnvelope
from services import role_service

logger = logging.getLogger("api.rbac_v2_router")

router = APIRouter()


# ─── v2 GET /tenants/{tenantId}/rbac/roles ───────────────────────────────────


@router.get(
    "/tenants/{tenantId}/rbac/roles",
    operation_id="listRolesV2",
    summary="角色與權限矩陣 — tenant-scoped v2（CR-0002-α）",
    response_model=RolesEnvelope,
    tags=["M17 RBAC"],
)
async def list_roles_v2(
    tenantId: str = Path(..., description="租戶 ID（UUID）"),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """GET /tenants/{tenantId}/rbac/roles — tenant-scoped v2。

    cross-tenant guard（ADR-0030）：path tenant 必須等於 JWT claim。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    roles = await role_service.list_roles(tenant_id=tenantId)
    return {"data": [Role(**r).model_dump(mode="json") for r in roles]}


# ─── v2 PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions ─────────────


class _UpdateRolePermissionsBodyV2(BaseModel):
    """對齊 v2 spec：PUT body（與 legacy PATCH body 結構相同）。"""

    permissions: list[str] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="扁平化權限碼清單（resource.action）",
    )
    reason: str = Field(..., min_length=4, max_length=500)


@router.put(
    "/tenants/{tenantId}/rbac/roles/{roleName}/permissions",
    operation_id="updateRolePermissionsV2",
    summary="動態調整角色權限 — tenant-scoped v2（CR-0002-α）",
    tags=["M17 RBAC"],
)
async def update_role_permissions_v2(
    tenantId: str = Path(..., description="租戶 ID（UUID）"),
    roleName: str = Path(..., description="角色 ID"),
    body: _UpdateRolePermissionsBodyV2 = Body(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions — tenant-scoped v2。

    cross-tenant guard + 呼叫既有 role_service.update_role_permissions（不重寫業務邏輯）。
    legacy PATCH /api/v1/roles/{role}/permissions 對應此端點（冪等語意，PUT 取代 PATCH）。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    try:
        result = await role_service.update_role_permissions(
            tenant_id=tenantId,
            role_name=roleName,
            desired_permissions=list(body.permissions),
            actor_id=user.user_id,
            actor_role=user.role,
            reason=body.reason,
        )
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("updateRolePermissionsV2 failed")
        raise ApiError(
            "INTERNAL_ERROR",
            f"role permissions update failed: {exc}",
            500,
        ) from exc

    return {"data": result}
