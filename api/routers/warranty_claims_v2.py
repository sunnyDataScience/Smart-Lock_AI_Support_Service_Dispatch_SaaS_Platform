"""Warranty Claims v2 router — spec-aligned tenant-scoped 保固申請端點（FR-0015 / CR-0003 P2）。

對齊 frozen spec path: POST /tenants/{tenantId}/warranty-claims（M13 Warranty）。
示範目標架構：
  - tenant-scoped path（非 /api/v1 flat）
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（HTTP Idempotency-Key header）
  - 呼既有 warranty_service.create_warranty_claim（零業務邏輯重寫）

舊 flat 路徑 POST /api/v1/warranty-claims（routers/warranty_claims.py）仍保留，
前端遷移後於後續波次移除（雙掛過渡，Never break userspace）。
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Response, Depends

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    WarrantyClaim,
    WarrantyClaimCreateRequest,
    WarrantyClaimEnvelope,
)
from services import warranty_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/warranty-claims",
    operation_id="createWarrantyClaimV2",
    summary="建立保固申請 — tenant-scoped v2（FR-0015 dual-trigger / CR-0003 P2）",
    response_model=WarrantyClaimEnvelope,
    status_code=201,
)
async def create_warranty_claim_v2(
    body: WarrantyClaimCreateRequest,
    response: Response,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard：path tenant 必須等於 JWT claim（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

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
        tenant_id=tenantId,
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
