"""Catalog v2 router — 報價主檔（CR-0034）。

  - GET /tenants/{tenantId}/quote-catalog  → 服務 + 材料 + 加價規則（internal cost RBAC 遮蔽）

數值為 esales mock；內部成本僅後台管理角色可見。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import quote_catalog_service

router = APIRouter()

_COST_VISIBLE_ROLES = {"admin", "operations_manager", "tenant_admin"}


@router.get(
    "/tenants/{tenantId}/quote-catalog",
    operation_id="getQuoteCatalogV2",
    summary="報價主檔 v2（服務/材料/加價規則；內部成本僅後台可見）",
    tags=["M04 Quote"],
)
async def get_quote_catalog_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)
    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
    return await quote_catalog_service.get_catalog(tenant_id=tenantId, include_cost=include_cost)
