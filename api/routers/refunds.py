"""Refunds router — listRefundRequests + getRefundRequest (read-only)。

operationId 對齊 openapi.yaml：listRefundRequests, getRefundRequest

不含 submitRefundDecision（雙簽寫入路徑，需 Idempotency-Key + 雙簽流程，不在本 phase）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
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
