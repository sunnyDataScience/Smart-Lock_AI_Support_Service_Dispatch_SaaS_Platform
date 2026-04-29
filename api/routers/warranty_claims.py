"""Warranty Claims router — list + get + submitWarrantyDecision。

operationId 對齊 openapi.yaml：
  listWarrantyClaims, getWarrantyClaim, submitWarrantyDecision

不含 createWarrantyClaim / submitEvidence 等寫入路徑。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    WarrantyClaim,
    WarrantyClaimEnvelope,
    WarrantyClaimPage,
    WarrantyClaimStatus,
    WarrantyDecision,
)
from services import warranty_service

router = APIRouter()


@router.get(
    "/warranty-claims",
    operation_id="listWarrantyClaims",
    summary="保固申請列表（cursor 分頁）",
    response_model=WarrantyClaimPage,
)
async def list_warranty_claims(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: WarrantyClaimStatus | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await warranty_service.list_warranty_claims(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        customer_id=customer_id,
        work_order_id=work_order_id,
    )
    return {
        "items": [WarrantyClaim(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/warranty-claims/{id}",
    operation_id="getWarrantyClaim",
    summary="保固申請詳情",
    response_model=WarrantyClaimEnvelope,
)
async def get_warranty_claim(
    id: str,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    claim = await warranty_service.get_warranty_claim(tenant_id=user.tenant_id, claim_id=id)
    return {"data": WarrantyClaim(**claim).model_dump(mode="json")}


@router.post(
    "/warranty-claims/{id}/decision",
    operation_id="submitWarrantyDecision",
    summary="保固審批決策（filed | in_progress → approved / rejected / in_progress）",
    response_model=WarrantyClaimEnvelope,
)
async def submit_warranty_decision(
    body: WarrantyDecision,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    decision_str = (
        body.decision.value if hasattr(body.decision, "value") else str(body.decision)
    )
    claim = await warranty_service.submit_decision(
        tenant_id=user.tenant_id,
        claim_id=id,
        decision=decision_str,
        resolution=body.resolution,
        discount_offered=body.discount_offered,
    )
    payload = {"data": WarrantyClaim(**claim).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
