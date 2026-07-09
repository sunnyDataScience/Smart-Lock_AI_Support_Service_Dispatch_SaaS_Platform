"""Pricing v2 router — tenant-scoped 計價計算端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M11 Pricing：
  - POST /tenants/{tenantId}/pricing/calculate → calculatePricingV2

CRUD 端點（listPricingRules / createPricingRule / updatePricingRule）保留在
legacy /api/v1/pricing/rules（routers/pricing_rules.py），加掛 Deprecation header
（D3，由 middleware 自動蓋），雙掛過渡；前端遷移後於 P3 波次移除（C-11）。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard 保護冪等性（CR-0002-α）
  - 呼既有 pricing_rule_service.calculate_pricing，零重寫 SQL
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    PricingCalculateRequest,
    PricingCalculateResponse,
)
from services import pricing_rule_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/pricing/calculate",
    operation_id="calculatePricingV2",
    summary="計算報價 v2（tenant-scoped，依 brand/lock_type/difficulty + 加成）",
    response_model=PricingCalculateResponse,
    tags=["M11 Pricing"],
)
async def calculate_pricing_v2(
    body: PricingCalculateRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await pricing_rule_service.calculate_pricing(
        tenant_id=tenantId,
        brand=body.brand,
        lock_type=body.lock_type.value,
        difficulty=body.difficulty.value,
        is_emergency=bool(body.is_emergency),
        is_night_service=bool(body.is_night_service),
        additional_items=list(body.additional_items) if body.additional_items else None,
    )

    payload = PricingCalculateResponse(**result).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, payload)
    return payload
