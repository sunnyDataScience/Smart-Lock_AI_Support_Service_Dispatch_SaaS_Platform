"""Warranty Claims router — list + get + create + submitWarrantyDecision。

operationId 對齊 openapi.yaml：
  listWarrantyClaims, getWarrantyClaim, createWarrantyClaim, submitWarrantyDecision

createWarrantyClaim 5/9 17:00 補（ADR-009 §8 D1 dual-trigger）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    WarrantyClaim,
    WarrantyClaimCreateRequest,
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


@router.post(
    "/warranty-claims",
    operation_id="createWarrantyClaim",
    summary="建立保固申請（F-015 dual-trigger）",
    response_model=WarrantyClaimEnvelope,
)
async def create_warranty_claim(
    body: WarrantyClaimCreateRequest,
    response: Response,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    claim_type = (
        body.claim_type.value
        if hasattr(body.claim_type, "value")
        else str(body.claim_type)
    )
    requested_by_role = (
        body.requested_by_role.value
        if hasattr(body.requested_by_role, "value")
        else str(body.requested_by_role)
    )
    purchase_date = (
        body.purchase_date.isoformat() if body.purchase_date else None
    )
    claim, created = await warranty_service.create_warranty_claim(
        tenant_id=user.tenant_id,
        customer_id=str(body.customer_id),
        device_brand=body.device_brand,
        device_model=body.device_model,
        claim_type=claim_type,
        requested_by_role=requested_by_role,
        work_order_id=str(body.work_order_id) if body.work_order_id else None,
        purchase_date=purchase_date,
        dispute_reason=body.dispute_reason,
    )
    response.status_code = 201 if created else 200
    payload = {"data": WarrantyClaim(**claim).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload


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
