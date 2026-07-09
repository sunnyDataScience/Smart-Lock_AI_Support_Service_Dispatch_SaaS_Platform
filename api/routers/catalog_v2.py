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

_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除


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


# ─────────────────────────────────────────────────────────────────────────────
# CR-0110 報價主檔 CRUD（20260702 會議裁決簡化版:一品牌一 DB → 單庫 code 唯一,
# 無 per-tenant 複合鍵/global+override）。業主 2026-07-03 裁決:三類目一次做、
# 軟刪、編輯後 is_mock=FALSE + decision_status='已確認'。
# 守衛對齊 pricing_rules_v2:OPS_ROLES + Idempotency-Key(POST) 。
# ─────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field  # noqa: E402

from core.deps import OPS_ROLES, role_required  # noqa: E402
from core.idempotency import IdempotencyContext, idempotency_guard  # noqa: E402

_KIND_BY_SEGMENT = {"services": "service", "materials": "material", "surcharges": "surcharge"}


class _CatalogItemBody(BaseModel):
    """三類目共用 body(白名單驗證在 service 層,依 kind 過濾)。

    code 僅 create 用;數值欄皆 ≥ 0(service 層驗)。
    """

    code: str | None = Field(default=None, max_length=40, description="類目代碼(create 必填)")
    category: str | None = None
    # service
    service_name: str | None = Field(default=None, max_length=120)
    service_type: str | None = None
    material_class: str | None = None
    needs_dispatch: str | None = None
    cross_zone: str | None = None
    internal_note: str | None = None
    internal_base_cost: float | None = None
    suggested_customer_price: float | None = None
    # material
    material_name: str | None = Field(default=None, max_length=120)
    spec_note: str | None = None
    needs_evidence: bool | None = None
    internal_cost: float | None = None
    suggested_price: float | None = None
    # surcharge
    rule_type: str | None = None
    rule_name: str | None = Field(default=None, max_length=120)
    condition_note: str | None = None
    amount: float | None = None
    value_text: str | None = None
    note: str | None = None
    # 共用
    unit: str | None = None


def _cross_tenant_write(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId does not match authenticated tenant", 403)


def _kind_of(segment: str) -> str:
    kind = _KIND_BY_SEGMENT.get(segment)
    if not kind:
        raise ApiError("NOT_FOUND", f"未知類目 {segment}", 404)
    return kind


@router.post(
    "/tenants/{tenantId}/quote-catalog/{segment}",
    operation_id="createQuoteCatalogItem",
    summary="新增報價主檔項目（services/materials/surcharges；CR-0110）",
    status_code=201,
    tags=["M04 Quote"],
)
async def create_quote_catalog_item(
    body: _CatalogItemBody,
    tenantId: str = Path(...),
    segment: str = Path(..., description="services | materials | surcharges"),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)
    result = await quote_catalog_service.create_item(
        kind=_kind_of(segment), tenant_id=tenantId,
        code=body.code or "", data=body.model_dump(exclude={"code"}, exclude_none=True),
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.patch(
    "/tenants/{tenantId}/quote-catalog/{segment}/{code}",
    operation_id="updateQuoteCatalogItem",
    summary="編輯報價主檔項目（partial；編輯後 is_mock=FALSE；CR-0110）",
    tags=["M04 Quote"],
)
async def update_quote_catalog_item(
    body: _CatalogItemBody,
    tenantId: str = Path(...),
    segment: str = Path(...),
    code: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _cross_tenant_write(user, tenantId)
    result = await quote_catalog_service.update_item(
        kind=_kind_of(segment), tenant_id=tenantId, code=code,
        data=body.model_dump(exclude={"code"}, exclude_none=True),
    )
    return {"data": result}


@router.delete(
    "/tenants/{tenantId}/quote-catalog/{segment}/{code}",
    operation_id="deleteQuoteCatalogItem",
    summary="刪除報價主檔項目（軟刪 deleted_at；CR-0110）",
    tags=["M04 Quote"],
)
async def delete_quote_catalog_item(
    tenantId: str = Path(...),
    segment: str = Path(...),
    code: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _cross_tenant_write(user, tenantId)
    result = await quote_catalog_service.delete_item(
        kind=_kind_of(segment), tenant_id=tenantId, code=code,
    )
    return {"data": result}
