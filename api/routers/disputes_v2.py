"""Dispute v2 router — dual-sign tenant-scoped 爭議端點（FR-0013 / CR-0004 §8）。

8 endpoints:
  1. GET  /tenants/{tenantId}/disputes                          → listDisputesV2
  2. GET  /tenants/{tenantId}/disputes/{disputeId}              → getDisputeV2
  3. POST /tenants/{tenantId}/disputes                          → openDisputeV2
  4. POST /tenants/{tenantId}/disputes/{disputeId}:review       → reviewDisputeV2
  5. POST /tenants/{tenantId}/disputes/{disputeId}:co-sign      → coSignDisputeV2
  6. POST /tenants/{tenantId}/disputes/{disputeId}:withdraw     → withdrawDisputeV2
  7. POST /tenants/{tenantId}/disputes/{disputeId}:escalate     → escalateDisputeV2
  8. POST /tenants/{tenantId}/disputes/{disputeId}:reopen       → reopenDisputeV2

dual-sign flow（HD-3）：
  step-1  X-Initiator = CSM review         → status: filed → in_review（或 mediation）
  step-2  X-Initiator = ops_manager co-sign → status: in_review|mediation → resolved

SoD（HD-3）：co-signer（X-Initiator on :co-sign）必須 ≠ reviewed_by，否則 403 SOD_VIOLATION。
cross-tenant guard（ADR-0030）：path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_*.

注意：本模組不使用 require_sod_actors（三維 SoD）——那是 single-call 雙簽；
本流程是跨兩個 call 的累積雙簽（review 存 reviewed_by，co-sign 存 cosigned_by）。
各 call 只需 X-Initiator（單一行為人 header），SoD 由 service 比對 reviewed_by ≠ cosigned_by。

HD-4（resolution_amount 負值 DGS/refund cascade）：
  service 層 co_sign_dispute() 已加 [DEFERRED] logger，本波次不觸發 cascade（ADR-0061/FR-0014）。

60d escalation cron（AC-03）：Phase II Cloud Scheduler；
  :escalate endpoint 提供手動升級（manual override）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from pydantic import BaseModel, Field

from core.deps import REVIEW_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import dispute_v2_service as svc

logger = logging.getLogger("api.disputes_v2")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Local helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    """X-Initiator header required（CSM on :review、ops_manager on :co-sign）。"""
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


# ─────────────────────────────────────────────────────────────────────────────
# Request body models
# ─────────────────────────────────────────────────────────────────────────────

class OpenDisputeBody(BaseModel):
    filed_by: str = Field(..., description="提交爭議的使用者 UUID")
    dispute_type: str = Field(
        ...,
        description="pricing|quality|warranty|cancellation_fee|settlement",
    )
    description: str | None = Field(default=None, description="爭議描述")
    work_order_id: str | None = Field(default=None, description="關聯工單 UUID（選填）")
    invoice_id: str | None = Field(default=None, description="關聯發票 UUID（選填）")
    evidence: dict | list | None = Field(default=None, description="佐證資料（jsonb，選填）")


class ReviewDisputeBody(BaseModel):
    proposed_resolution: str = Field(..., min_length=1, description="CSM 提案解決方案")
    resolution_amount: float | None = Field(default=None, description="提案金額（選填）")
    to_mediation: bool = Field(default=False, description="True 則 status 改為 mediation 而非 in_review")


class CoSignDisputeBody(BaseModel):
    resolution: str = Field(..., min_length=5, description="最終解決方案（最少 5 字）")
    resolution_amount: float | None = Field(
        default=None,
        description="最終金額（選填；負值→DGS/refund cascade DEFERRED Phase II）",
    )


class WithdrawDisputeBody(BaseModel):
    reason: str | None = Field(default=None, description="撤銷原因（選填）")


class EscalateDisputeBody(BaseModel):
    reason: str | None = Field(default=None, description="升級原因（選填）")


class ReopenDisputeBody(BaseModel):
    description: str | None = Field(default=None, description="新爭議描述（選填，繼承原 dispute 若未提供）")
    dispute_type: str | None = Field(
        default=None,
        description="新爭議類型（選填；未提供則繼承原 dispute）",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /tenants/{tenantId}/disputes
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/disputes",
    operation_id="listDisputesV2",
    summary="列爭議單（tenant-scoped v2，cursor 分頁）",
    response_model=dict,
)
async def list_disputes_v2(
    tenantId: str = Path(...),
    status: str | None = Query(
        default=None,
        description="filed|in_review|mediation|resolved|escalated|closed_withdrawn",
    ),
    dispute_type: str | None = Query(
        default=None,
        description="pricing|quality|warranty|cancellation_fee|settlement",
    ),
    work_order_id: str | None = Query(default=None, description="工單 UUID filter"),
    cursor: str | None = Query(default=None, description="上頁末 cursor（opaque base64）"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await svc.list_disputes_v2(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        status=status,
        dispute_type=dispute_type,
        work_order_id=work_order_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenantId}/disputes/{disputeId}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/disputes/{disputeId}",
    operation_id="getDisputeV2",
    summary="取單筆爭議（tenant-scoped v2）",
    response_model=dict,
)
async def get_dispute_v2(
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.get_dispute_v2(tenant_id=tenantId, dispute_id=disputeId)
    return {"data": dispute}


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /tenants/{tenantId}/disputes
#    新建 dispute（status=filed, sla_deadline=now+60d）
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes",
    operation_id="openDisputeV2",
    summary="開立爭議（status=filed, sla_deadline=now+60d）",
    status_code=201,
    response_model=dict,
)
async def open_dispute_v2(
    body: OpenDisputeBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.open_dispute(
        tenant_id=tenantId,
        filed_by=body.filed_by,
        dispute_type=body.dispute_type,
        description=body.description,
        work_order_id=body.work_order_id,
        invoice_id=body.invoice_id,
        evidence=body.evidence,
    )

    payload = {"data": dispute}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /tenants/{tenantId}/disputes/{disputeId}:review
#    step-1 CSM review：filed → in_review（或 mediation）
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes/{disputeId}:review",
    operation_id="reviewDisputeV2",
    summary="CSM review（step-1，filed → in_review 或 mediation）",
    response_model=dict,
)
async def review_dispute_v2(
    body: ReviewDisputeBody,
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES, fail_closed=True)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.review_dispute(
        tenant_id=tenantId,
        dispute_id=disputeId,
        reviewer_id=initiator,
        proposed_resolution=body.proposed_resolution,
        resolution_amount=body.resolution_amount,
        to_mediation=body.to_mediation,
    )

    payload = {"data": dispute}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST /tenants/{tenantId}/disputes/{disputeId}:co-sign
#    step-2 ops_manager co-sign：in_review|mediation → resolved
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes/{disputeId}:co-sign",
    operation_id="coSignDisputeV2",
    summary="ops_manager co-sign（step-2，in_review|mediation → resolved）",
    response_model=dict,
)
async def co_sign_dispute_v2(
    body: CoSignDisputeBody,
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES, fail_closed=True)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """HD-4：resolution_amount < 0 → service 層記 [DEFERRED] logger，不觸發 DGS/refund cascade。"""
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.co_sign_dispute(
        tenant_id=tenantId,
        dispute_id=disputeId,
        co_signer_id=initiator,
        resolution=body.resolution,
        resolution_amount=body.resolution_amount,
    )

    payload = {"data": dispute}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 6. POST /tenants/{tenantId}/disputes/{disputeId}:withdraw
#    filed/in_review/mediation → closed_withdrawn
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes/{disputeId}:withdraw",
    operation_id="withdrawDisputeV2",
    summary="撤銷爭議（filed|in_review|mediation → closed_withdrawn）",
    response_model=dict,
)
async def withdraw_dispute_v2(
    body: WithdrawDisputeBody,
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.withdraw_dispute(
        tenant_id=tenantId,
        dispute_id=disputeId,
        reason=body.reason,
    )

    payload = {"data": dispute}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 7. POST /tenants/{tenantId}/disputes/{disputeId}:escalate
#    手動升級（filed/in_review/mediation → escalated）
#    60d 自動 escalation = Phase II Cloud Scheduler（_escalate_overdue_disputes helper）
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes/{disputeId}:escalate",
    operation_id="escalateDisputeV2",
    summary="手動升級爭議（filed|in_review|mediation → escalated）",
    response_model=dict,
)
async def escalate_dispute_v2(
    body: EscalateDisputeBody,
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    dispute = await svc.escalate_dispute(
        tenant_id=tenantId,
        dispute_id=disputeId,
        escalated_by=initiator,
        reason=body.reason,
    )

    payload = {"data": dispute}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 8. POST /tenants/{tenantId}/disputes/{disputeId}:reopen
#    AC-05 reopen：原 dispute resolved/closed_withdrawn → 新建 dispute（parent_dispute_id=原 id）
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/disputes/{disputeId}:reopen",
    operation_id="reopenDisputeV2",
    summary="重開爭議（resolved|closed_withdrawn → 新 dispute w/ parent_dispute_id）",
    status_code=201,
    response_model=dict,
)
async def reopen_dispute_v2(
    body: ReopenDisputeBody,
    tenantId: str = Path(...),
    disputeId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """AC-05：不可直接 reopen 已關閉 dispute；必須新建 dispute 引用 parent_dispute_id。

    201 回新 dispute（filed 狀態，parent_dispute_id=原 disputeId）。
    409 STATE_CONFLICT 若原 dispute 非 resolved/closed_withdrawn。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    new_dispute = await svc.reopen_dispute(
        tenant_id=tenantId,
        dispute_id=disputeId,
        filed_by=user.user_id or "",
        description=body.description,
        dispute_type=body.dispute_type,
    )

    payload = {"data": new_dispute}
    if idem is not None:
        await idem.save(201, payload)
    return payload
