"""Pricing Rules router — listPricingRules (read-only)。

operationId 對齊 openapi.yaml：listPricingRules

不含 createPricingRule / updatePricingRule / calculatePricing 等寫入路徑。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    PricingRule,
    PricingRulePage,
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
