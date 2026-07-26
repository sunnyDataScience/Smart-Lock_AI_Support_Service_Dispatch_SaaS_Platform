"""Reconciliations router — listReconciliations + approveReconciliation + rejectReconciliation。

operationId 對齊 openapi.yaml：
  listReconciliations, approveReconciliation, rejectReconciliation（UAT-0718 W1-2）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import OPS_ROLES, REVIEW_ROLES, CurrentUser, require_tenant, role_required
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    Reconciliation,
    ReconciliationApproveRequest,
    ReconciliationPage,
    ReconciliationRejectRequest,
    ReconciliationStatus,
    Settlement,
)
from services import reconciliation_service

router = APIRouter()


@router.get(
    "/accounting/reconciliations",
    operation_id="listReconciliations",
    summary="對帳記錄列表（cursor 分頁）",
    response_model=ReconciliationPage,
)
async def list_reconciliations(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: ReconciliationStatus | None = Query(default=None),
    technician_id: str | None = Query(default=None),
    # CR-0183 補漏（2026-07-27）：v2 孿生端點已上守衛、本 legacy 端點漏掛，
    # 兩者皆掛載 → 低權限角色改打 legacy 路徑即可繞過。對齊 v2 守衛。
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    page = await reconciliation_service.list_reconciliations(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        technician_id=technician_id,
    )
    return {
        "items": [Reconciliation(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/accounting/reconciliations/{id}/approve",
    operation_id="approveReconciliation",
    summary="核准對帳並建立結算（pending → approved + settlement INSERT）",
)
async def approve_reconciliation(
    body: ReconciliationApproveRequest | None = None,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    note = body.note if body else None
    result = await reconciliation_service.approve_reconciliation(
        tenant_id=user.tenant_id,
        recon_id=id,
        approver_user_id=user.user_id,
        note=note,
    )
    payload = {
        "reconciliation": Reconciliation(**result["reconciliation"]).model_dump(mode="json"),
        "settlement": Settlement(**result["settlement"]).model_dump(mode="json"),
    }
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/accounting/reconciliations/{id}:reject",
    operation_id="rejectReconciliation",
    summary="駁回對帳（pending → rejected + 審計欄位；UAT-0718 W1-2）",
)
async def reject_reconciliation(
    body: ReconciliationRejectRequest,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """僅 pending 可駁（其餘 409，語意同 approve）；reason ≥3 字必填。"""
    result = await reconciliation_service.reject_reconciliation(
        tenant_id=user.tenant_id,
        recon_id=id,
        rejecter_user_id=user.user_id,
        reason=body.reason,
    )
    payload = {
        "reconciliation": Reconciliation(**result["reconciliation"]).model_dump(mode="json"),
    }
    if idem is not None:
        await idem.save(200, payload)
    return payload
