"""Reconciliations router — listReconciliations + approveReconciliation。

operationId 對齊 openapi.yaml：
  listReconciliations, approveReconciliation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    Reconciliation,
    ReconciliationApproveRequest,
    ReconciliationPage,
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
    user: CurrentUser = Depends(require_tenant),
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
