"""Pricing Rules router — list / create / update / calculate。

operationId 對齊 openapi.yaml：
  listPricingRules, createPricingRule, updatePricingRule, calculatePricing
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    PricingCalculateRequest,
    PricingCalculateResponse,
    PricingRule,
    PricingRuleCreateRequest,
    PricingRulePage,
    PricingRuleUpdateRequest,
)
from services import pricing_rule_service

router = APIRouter()


@router.get(
    "/pricing/rules",
    operation_id="listPricingRules",
    summary="計價規則列表（cursor 分頁）",
    response_model=PricingRulePage,
)
async def list_pricing_rules(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    brand: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await pricing_rule_service.list_pricing_rules(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        brand=brand,
    )
    return {
        "items": [PricingRule(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/pricing/rules",
    operation_id="createPricingRule",
    summary="建立計價規則",
    status_code=201,
)
async def create_pricing_rule(
    body: PricingRuleCreateRequest,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    surcharges_payload = (
        [s.model_dump(mode="json") for s in body.surcharges]
        if body.surcharges
        else None
    )
    rule = await pricing_rule_service.create_pricing_rule(
        tenant_id=user.tenant_id,
        brand=body.brand,
        lock_type=body.lock_type.value,
        difficulty=body.difficulty.value,
        base_price=body.base_price,
        surcharges=surcharges_payload,
    )
    payload = {"data": PricingRule(**rule).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.put(
    "/pricing/rules/{id}",
    operation_id="updatePricingRule",
    summary="更新計價規則（base_price / surcharges）",
)
async def update_pricing_rule(
    body: PricingRuleUpdateRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    surcharges_payload = (
        [s.model_dump(mode="json") for s in body.surcharges]
        if body.surcharges is not None
        else None
    )
    rule = await pricing_rule_service.update_pricing_rule(
        tenant_id=user.tenant_id,
        rule_id=id,
        base_price=body.base_price,
        surcharges=surcharges_payload,
    )
    return {"data": PricingRule(**rule).model_dump(mode="json")}


@router.post(
    "/pricing/calculate",
    operation_id="calculatePricing",
    summary="計算報價（依 brand/lock_type/difficulty + 加成）",
    response_model=PricingCalculateResponse,
)
async def calculate_pricing(
    body: PricingCalculateRequest,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    result = await pricing_rule_service.calculate_pricing(
        tenant_id=user.tenant_id,
        brand=body.brand,
        lock_type=body.lock_type.value,
        difficulty=body.difficulty.value,
        is_emergency=bool(body.is_emergency),
        is_night_service=bool(body.is_night_service),
        additional_items=list(body.additional_items)
        if body.additional_items
        else None,
    )
    return PricingCalculateResponse(**result).model_dump(mode="json")
