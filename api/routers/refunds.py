"""Refunds router — list/get + submitRefundDecision。

operationId 對齊 openapi.yaml：listRefundRequests, getRefundRequest, submitRefundDecision

雙簽流程簡化：MVP 不分 csm/ops 兩段，approve 一律單步推進到 'approved'。
詳見 services/refund_service.py 模組註解。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    RefundDecision,
    RefundEnvelope,
    RefundRequest,
    RefundRequestEnvelope,
    RefundRequestPage,
    RefundRequestStatus,
)
from services import refund_service

router = APIRouter()


@router.get(
    "/refunds",
    operation_id="listRefundRequests",
    summary="退款申請列表（cursor 分頁）",
    response_model=RefundRequestPage,
)
async def list_refund_requests(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: RefundRequestStatus | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await refund_service.list_refund_requests(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        work_order_id=work_order_id,
    )
    return {
        "items": [RefundRequest(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/refunds/{id}",
    operation_id="getRefundRequest",
    summary="退款申請詳情",
    response_model=RefundRequestEnvelope,
)
async def get_refund_request(
    id: str,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    refund = await refund_service.get_refund_request(tenant_id=user.tenant_id, refund_id=id)
    return {"data": RefundRequest(**refund).model_dump(mode="json")}


@router.post(
    "/refunds/{id}/decision",
    operation_id="submitRefundDecision",
    summary="退款審批決策（pending → approved/rejected/escalated）",
    response_model=RefundEnvelope,
)
async def submit_refund_decision(
    body: RefundDecision,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    decision_str = (
        body.decision.value if hasattr(body.decision, "value") else str(body.decision)
    )
    refund = await refund_service.submit_decision(
        tenant_id=user.tenant_id,
        refund_id=id,
        decision=decision_str,
        reason=body.reason,
        decided_by_user_id=user.user_id,
    )
    payload = {"data": RefundRequest(**refund).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
