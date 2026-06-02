"""Pricing Rules v2 router — tenant-scoped pricing CRUD（Track B S4 / CR-0004 §8 C3）。

4 endpoints:
  1. GET  /tenants/{tenantId}/pricing/rules                → listPricingRulesV2
  2. GET  /tenants/{tenantId}/pricing/rules/{ruleId}       → getPricingRuleV2
  3. POST /tenants/{tenantId}/pricing/rules                → createPricingRuleV2
  4. PUT  /tenants/{tenantId}/pricing/rules/{ruleId}       → updatePricingRuleV2

路徑 C 混合過渡（CR-0004 §8 C3）：
  - CRUD 立即可用，每次 mutation 並寫 saas.change_request（type_code='pricing_rule'）。
  - X-Initiator header 為 mutation 必填（記 change_request.created_by）。
  - cross-tenant guard：path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_*（ADR-0030）。
  - Idempotency-Key header 於 POST/PUT 支援 dedup。
  - calculate v2 已存在於 pricing_v2.py，本模組不動 calculate。
  - legacy pricing_rule_service / public.price_rules / pricing_rules.py 完全不動。

HD-4 follow-up：
  calculate v2 入參格式 spec pc_id/contract vs code brand/lock_type domain model 分歧，
  屬 calculate 範疇，標 follow-up CR。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import pricing_rule_v2_service as svc

logger = logging.getLogger("api.pricing_rules_v2")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Local helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    """X-Initiator header required for mutation endpoints（記 change_request.created_by）。"""
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


# ─────────────────────────────────────────────────────────────────────────────
# Request body models
# ─────────────────────────────────────────────────────────────────────────────


class PricingRuleBody(BaseModel):
    brand: str = Field(..., min_length=1, description="品牌（必填）")
    lock_type: str = Field(..., min_length=1, description="鎖具類型（必填）")
    difficulty: str | None = Field(default=None, description="難度（選填；easy/medium/hard）")
    base_price: float | str = Field(..., description="基本費用（decimal string 或 number，非負）")
    labor_cost: float | str | None = Field(default=None, description="工資（decimal string 或 number，選填）")
    parts_cost: float | str | None = Field(default=None, description="零件費用（decimal string 或 number，選填）")
    modifiers: list | None = Field(default=None, description="附加費用（PricingSurcharge[]，選填）")
    reason: str | None = Field(default=None, description="變更原因（選填；記入 change_request）")


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /tenants/{tenantId}/pricing/rules
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/pricing/rules",
    operation_id="listPricingRulesV2",
    summary="列計價規則（tenant-scoped v2，cursor 分頁）",
    response_model=dict,
)
async def list_pricing_rules_v2(
    tenantId: str = Path(...),
    brand: str | None = Query(default=None, description="品牌過濾（大小寫不敏感）"),
    lock_type: str | None = Query(default=None, description="鎖具類型過濾"),
    is_active: bool | None = Query(default=None, description="是否啟用（預設只回傳 True）"),
    cursor: str | None = Query(default=None, description="上頁末 cursor（opaque base64）"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.list_pricing_rules_v2(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        brand=brand,
        lock_type=lock_type,
        is_active=is_active,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenantId}/pricing/rules/{ruleId}
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/pricing/rules/{ruleId}",
    operation_id="getPricingRuleV2",
    summary="取單筆計價規則（tenant-scoped v2）",
    response_model=dict,
)
async def get_pricing_rule_v2(
    tenantId: str = Path(...),
    ruleId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    rule = await svc.get_pricing_rule_v2(tenant_id=tenantId, rule_id=ruleId)
    return {"data": rule}


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /tenants/{tenantId}/pricing/rules
#    建立計價規則 + 並寫 change_request governance 審計
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/pricing/rules",
    operation_id="createPricingRuleV2",
    summary="建立計價規則（tenant-scoped v2，並寫 change_request 審計）",
    response_model=dict,
    status_code=201,
)
async def create_pricing_rule_v2(
    body: PricingRuleBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    rule = await svc.create_pricing_rule_v2(
        tenant_id=tenantId,
        brand=body.brand,
        lock_type=body.lock_type,
        difficulty=body.difficulty,
        base_price=body.base_price,
        labor_cost=body.labor_cost,
        parts_cost=body.parts_cost,
        modifiers=body.modifiers,
        reason=body.reason,
        created_by=initiator,
    )

    payload = {"data": rule}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. PUT /tenants/{tenantId}/pricing/rules/{ruleId}
#    全量更新計價規則 + 並寫 change_request governance 審計
# ─────────────────────────────────────────────────────────────────────────────


@router.put(
    "/tenants/{tenantId}/pricing/rules/{ruleId}",
    operation_id="updatePricingRuleV2",
    summary="更新計價規則（tenant-scoped v2 全量，並寫 change_request 審計）",
    response_model=dict,
)
async def update_pricing_rule_v2(
    body: PricingRuleBody,
    tenantId: str = Path(...),
    ruleId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    rule = await svc.update_pricing_rule_v2(
        tenant_id=tenantId,
        rule_id=ruleId,
        brand=body.brand,
        lock_type=body.lock_type,
        difficulty=body.difficulty,
        base_price=body.base_price,
        labor_cost=body.labor_cost,
        parts_cost=body.parts_cost,
        modifiers=body.modifiers,
        reason=body.reason,
        created_by=initiator,
    )

    payload = {"data": rule}
    if idem is not None:
        await idem.save(200, payload)
    return payload
