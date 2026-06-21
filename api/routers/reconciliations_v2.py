"""Reconciliation v2 router — dual-sign tenant-scoped 對帳端點（FR-0013 / CR-0004 §8）。

4 endpoints:
  1. GET  /tenants/{tenantId}/accounting/reconciliations               → listReconciliationsV2
  2. GET  /tenants/{tenantId}/accounting/reconciliations/{reconId}     → getReconciliationV2
  3. POST /tenants/{tenantId}/accounting/reconciliations/{reconId}:review    → reviewReconciliationV2
  4. POST /tenants/{tenantId}/accounting/reconciliations/{reconId}:co-sign   → coSignReconciliationV2

dual-sign flow（HD-2 / HD-3）：
  step-1  X-Initiator = CSM review         → status: pending → in_review
  step-2  X-Initiator = ops_manager co-sign → status: in_review → approved + settlement INSERT

SoD（HD-2）：co-signer（X-Initiator on :co-sign）必須 ≠ reviewed_by，否則 403 SOD_VIOLATION。
cross-tenant guard（ADR-0030）：path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_*.

注意：本模組不使用 require_sod_actors（三維 SoD）——那是 single-call 雙簽；
本流程是跨兩個 call 的累積雙簽（review 存 reviewed_by，co-sign 存 approved_by）。
各 call 只需 X-Initiator（單一行為人 header），SoD 由 service 比對 reviewed_by ≠ approved_by。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import reconciliation_v2_service as svc

logger = logging.getLogger("api.reconciliations_v2")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Local helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    """X-Initiator header required（CSM on review、ops_manager on co-sign）。"""
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


class ReviewBody(BaseModel):
    note: str | None = None


class CoSignBody(BaseModel):
    note: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /tenants/{tenantId}/accounting/reconciliations
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/accounting/reconciliations",
    operation_id="listReconciliationsV2",
    summary="列對帳單（tenant-scoped v2，cursor 分頁）",
    response_model=dict,
)
async def list_reconciliations_v2(
    tenantId: str = Path(...),
    status: str | None = Query(default=None, description="pending|in_review|approved|disputed"),
    technician_id: str | None = Query(default=None, description="技師 UUID filter"),
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

    result = await svc.list_reconciliations_v2(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        status=status,
        technician_id=technician_id,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenantId}/accounting/reconciliations/{reconId}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/accounting/reconciliations/{reconId}",
    operation_id="getReconciliationV2",
    summary="取單筆對帳單（tenant-scoped v2）",
    response_model=dict,
)
async def get_reconciliation_v2(
    tenantId: str = Path(...),
    reconId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    recon = await svc.get_reconciliation_v2(tenant_id=tenantId, recon_id=reconId)
    return {"data": recon}


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /tenants/{tenantId}/accounting/reconciliations/{reconId}:review
#    step-1 CSM review：pending → in_review
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliations/{reconId}:review",
    operation_id="reviewReconciliationV2",
    summary="CSM review（step-1，pending → in_review）",
    response_model=dict,
)
async def review_reconciliation_v2(
    body: ReviewBody,
    tenantId: str = Path(...),
    reconId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    recon = await svc.review_reconciliation(
        tenant_id=tenantId,
        recon_id=reconId,
        reviewer_id=initiator,
        note=body.note,
    )

    payload = {"data": recon}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /tenants/{tenantId}/accounting/reconciliations/{reconId}:co-sign
#    step-2 ops_manager co-sign：in_review → approved + settlement INSERT
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliations/{reconId}:co-sign",
    operation_id="coSignReconciliationV2",
    summary="ops_manager co-sign（step-2，in_review → approved + settlement）",
    response_model=dict,
)
async def co_sign_reconciliation_v2(
    body: CoSignBody,
    tenantId: str = Path(...),
    reconId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.co_sign_reconciliation(
        tenant_id=tenantId,
        recon_id=reconId,
        co_signer_id=initiator,
        note=body.note,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload
