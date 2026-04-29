"""Roles router — read-only 角色與權限矩陣。

operationId 對齊 openapi.yaml：
  - listRoles — 5 系統角色 + 各角色於本租戶的使用者數 + 權限矩陣

未來擴充（不在本 phase 範圍）：
  - 自訂角色 CRUD（需 roles 表）
  - 權限矩陣編輯（需 role_permissions 表）
  - 角色指派 / 撤銷端點
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.deps import CurrentUser, require_tenant
from models.generated import Role, RolesEnvelope
from services import role_service

router = APIRouter()


@router.get(
    "/roles",
    operation_id="listRoles",
    summary="角色與權限矩陣（read-only；含本租戶各角色使用者數）",
    response_model=RolesEnvelope,
)
async def list_roles(user: CurrentUser = Depends(require_tenant)) -> dict:
    roles = await role_service.list_roles(tenant_id=user.tenant_id)
    return {"data": [Role(**r).model_dump(mode="json") for r in roles]}
