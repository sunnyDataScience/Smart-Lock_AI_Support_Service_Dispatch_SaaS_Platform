"""Reconciliation Exception v2 router — CR-0018 Stage 2 Flow 13 EX5 端點。

7 endpoints（tenant-scoped）：
  1. GET  /tenants/{tenantId}/accounting/reconciliation-exceptions
                                                  → listReconciliationExceptions
  2. GET  /tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}
                                                  → getReconciliationException
  3. POST .../{excId}:advance                     → 偵測 detected → ops_review
  4. POST .../{excId}:propose-fix  (X-Initiator)  → step-1 CSM 提案 fix_path
  5. POST .../{excId}:approve-fix  (X-Initiator)  → step-2 ops_manager 核准 (SoD)
  6. POST .../{excId}:apply-fix    (X-Initiator)  → 套用修正；voucher_reverse
                                                    路徑會先呼 voucher_void_service
                                                    產 reverse voucher 再回填 id
  7. POST .../{excId}:close        (X-Initiator)  → applied / detected /
                                                    ops_review / fix_proposed → closed

對齊 reconciliations_v2 router pattern：
- X-Initiator header 強制（service action）
- cross-tenant guard ADR-0030
- Idempotency-Key 支援（idempotency_guard）
- SoD（HD-4=a）：approver ≠ proposer → 403 SOD_VIOLATION
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import (
    reconciliation_exception_service as svc,
    voucher_void_service,
)

logger = logging.getLogger("api.reconciliation_exceptions_v2")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


# ─────────────────────────────────────────────────────────────────────────────
# Bodies
# ─────────────────────────────────────────────────────────────────────────────

class ProposeFixBody(BaseModel):
    fix_path: str  # invoice_supplement | recon_void | voucher_reverse
    resolution_note: str | None = None


class ApproveFixBody(BaseModel):
    note: str | None = None


class ApplyFixBody(BaseModel):
    """Stage 2: voucher_reverse 路徑帶 voucher_id（要被沖銷的原 voucher）。

    invoice_supplement 路徑要求已建好的 invoice_id（補單流程在 ops 後台另跑）。
    recon_void 路徑兩者皆可省。
    """
    voucher_id: str | None = None       # voucher_reverse 路徑要被沖銷的目標
    void_reason: str | None = "error_correction"  # voucher_void_service 接受
    void_comment: str | None = None
    invoice_id: str | None = None       # invoice_supplement 路徑補的 invoice
    note: str | None = None


class CloseBody(BaseModel):
    resolution_note: str | None = None


class DetectBody(BaseModel):
    """偵測入口 body — HD-5 三來源 (upload_realtime / cron_daily / manual) 均走此端點。

    Internal callers（upload service / cron job）直接呼 svc.detect_exception；
    本端點主要給：(a) 手動補建 detected_by='manual'；
                 (b) cron 走 internal API 模式（若部署模型如此）。
    """
    reconciliation_id: str
    exception_kind: str
    description: str
    detected_by: str = "manual"
    amount_delta: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET list
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions:detect",
    operation_id="detectReconciliationException",
    summary="偵測寫入新例外（status=detected）；冪等",
    response_model=dict,
    status_code=201,
)
async def detect_exception_endpoint(
    body: DetectBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.detect_exception(
        tenant_id=tenantId,
        reconciliation_id=body.reconciliation_id,
        exception_kind=body.exception_kind,
        description=body.description,
        detected_by=body.detected_by,
        amount_delta=body.amount_delta,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.get(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions",
    operation_id="listReconciliationExceptions",
    summary="列對帳異常（cursor 分頁）",
    response_model=dict,
)
async def list_exceptions(
    tenantId: str = Path(...),
    status: str | None = Query(default=None),
    reconciliation_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_exceptions(
        tenant_id=tenantId, status=status,
        reconciliation_id=reconciliation_id, cursor=cursor, limit=limit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET single
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}",
    operation_id="getReconciliationException",
    summary="取單筆對帳異常",
    response_model=dict,
)
async def get_exception(
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return {"data": await svc.get_exception(tenant_id=tenantId, exception_id=excId)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST :advance   detected → ops_review
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}:advance",
    operation_id="advanceReconciliationException",
    summary="例外進入 review 階段（detected → ops_review）",
    response_model=dict,
)
async def advance_exception(
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.advance_to_review(tenant_id=tenantId, exception_id=excId)
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST :propose-fix   step-1 CSM 提案
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}:propose-fix",
    operation_id="proposeReconciliationExceptionFix",
    summary="step-1 CSM 提出修正方案（detected/ops_review → fix_proposed）",
    response_model=dict,
)
async def propose_fix(
    body: ProposeFixBody,
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.propose_fix(
        tenant_id=tenantId, exception_id=excId, actor_id=initiator,
        fix_path=body.fix_path, resolution_note=body.resolution_note,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST :approve-fix   step-2 ops_manager 核准（SoD）
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}:approve-fix",
    operation_id="approveReconciliationExceptionFix",
    summary="step-2 ops_manager 核准修正（fix_proposed → fix_approved，SoD）",
    response_model=dict,
)
async def approve_fix(
    body: ApproveFixBody,
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.approve_fix(
        tenant_id=tenantId, exception_id=excId, actor_id=initiator,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 6. POST :apply-fix   套用修正
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}:apply-fix",
    operation_id="applyReconciliationExceptionFix",
    summary="套用修正（fix_approved → applied）；voucher_reverse 路徑連動 voucher_void",
    response_model=dict,
)
async def apply_fix(
    body: ApplyFixBody,
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)

    # 先取目前 exception 看 fix_path
    current = await svc.get_exception(tenant_id=tenantId, exception_id=excId)
    fix_path = current.get("fix_path")
    if fix_path is None:
        raise ApiError(
            "STATE_CONFLICT", "fix_path not set; propose_fix first", 409,
        )

    applied_voucher_id = None
    applied_invoice_id = None

    if fix_path == "voucher_reverse":
        # 連動：呼 voucher_void_service 產 reverse voucher
        if not body.voucher_id:
            raise ApiError(
                "VALIDATION_ERROR",
                "voucher_id required for voucher_reverse path",
                422,
            )
        reverse = await voucher_void_service.void_voucher(
            voucher_id=body.voucher_id,
            reason=body.void_reason or "error_correction",
            comment=body.void_comment or f"EX5 exception {excId[:8]} fix",
            keeper_user_id=initiator,
        )
        applied_voucher_id = reverse.get("id")
        logger.info(
            "EX5 voucher_reverse: exc=%s voucher_orig=%s voucher_reverse=%s",
            excId[:8], body.voucher_id[:8],
            (applied_voucher_id or "?")[:8],
        )
    elif fix_path == "invoice_supplement":
        if not body.invoice_id:
            raise ApiError(
                "VALIDATION_ERROR",
                "invoice_id required for invoice_supplement path",
                422,
            )
        applied_invoice_id = body.invoice_id

    result = await svc.apply_fix(
        tenant_id=tenantId, exception_id=excId,
        applied_voucher_id=applied_voucher_id,
        applied_invoice_id=applied_invoice_id,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 7. POST :close   多前態 → closed
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/reconciliation-exceptions/{excId}:close",
    operation_id="closeReconciliationException",
    summary="結案（applied / detected / ops_review / fix_proposed → closed）",
    response_model=dict,
)
async def close_exception(
    body: CloseBody,
    tenantId: str = Path(...),
    excId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.close_exception(
        tenant_id=tenantId, exception_id=excId,
        resolution_note=body.resolution_note,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload
