"""Catalog v2 router — 報價主檔（CR-0034）。

  - GET /tenants/{tenantId}/quote-catalog  → 服務 + 材料 + 加價規則（internal cost RBAC 遮蔽）

數值為 esales mock；內部成本僅後台管理角色可見。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from fastapi import Query

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import payout_rule_service, quote_catalog_service

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


@router.get(
    "/tenants/{tenantId}/payout-rules",
    operation_id="listPayoutRulesV2",
    summary="師傅拆帳規則主檔 v2（CR-0037；base_payout 僅後台可見）",
    tags=["M12 Settlement"],
)
async def list_payout_rules_v2(
    tenantId: str = Path(...),
    service_code: str | None = Query(default=None, description="篩選單一服務"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)
    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
    rules = await payout_rule_service.list_rules(
        tenant_id=tenantId, include_cost=include_cost, service_code=service_code)
    return {"data": rules, "cost_visible": include_cost,
            "note": "esales sheet21 mock；內部拆帳成本僅後台角色可見，正式值待 esales Q-09 師傅分潤"}
