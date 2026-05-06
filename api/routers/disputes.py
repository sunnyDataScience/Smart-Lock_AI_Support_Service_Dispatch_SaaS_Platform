"""Disputes router — listDisputes + getDispute (read-only)。

operationId 對齊 openapi.yaml：listDisputes, getDispute

不含 submitDisputeResolution（write 路徑，需 Idempotency-Key + 證據檔案上傳，
不在本 phase；待 dispute write endpoints + media upload 上線後接入）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    Dispute,
    DisputeEnvelope,
    DisputePage,
    DisputeStatus,
    DisputeType,
)
from services import dispute_service

router = APIRouter()


@router.get(
    "/disputes",
    operation_id="listDisputes",
    summary="爭議案件列表（cursor 分頁）",
    response_model=DisputePage,
)
async def list_disputes(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: DisputeStatus | None = Query(default=None),
    dispute_type: DisputeType | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await dispute_service.list_disputes(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        dispute_type=dispute_type.value if dispute_type else None,
        work_order_id=work_order_id,
    )
    return {
        "items": [Dispute(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/disputes/{id}",
    operation_id="getDispute",
    summary="爭議案件詳情",
    response_model=DisputeEnvelope,
)
async def get_dispute(
    id: str,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    dispute = await dispute_service.get_dispute(tenant_id=user.tenant_id, dispute_id=id)
    return {"data": Dispute(**dispute).model_dump(mode="json")}


# =============================================================================
# Dispute decision (resolve / escalate / reject)
# =============================================================================

from typing import Literal as _Literal  # noqa: E402

from fastapi import Path  # noqa: E402
from pydantic import BaseModel as _BaseModel, Field as _Field  # noqa: E402

from core.idempotency import IdempotencyContext, idempotency_guard  # noqa: E402


class _DecisionRequest(_BaseModel):
    decision: _Literal["resolve", "escalate", "reject"]
    resolution: str = _Field(..., min_length=5, max_length=2000)
    resolution_amount: float | None = _Field(default=None)


@router.post(
    "/disputes/{id}/decision",
    operation_id="submitDisputeDecision",
    summary="提交爭議仲裁決定（filed/under_review/mediation → resolved/escalated）",
    response_model=DisputeEnvelope,
)
async def submit_dispute_decision(
    body: _DecisionRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    dispute = await dispute_service.submit_decision(
        tenant_id=user.tenant_id,
        dispute_id=id,
        decision=body.decision,
        resolution=body.resolution,
        resolution_amount=body.resolution_amount,
        resolver_user_id=user.user_id,
    )
    payload = {"data": Dispute(**dispute).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
