"""Refunds router — list/get + submitRefundDecision。

operationId 對齊 openapi.yaml：listRefundRequests, getRefundRequest, submitRefundDecision

雙簽流程簡化：MVP 不分 csm/ops 兩段，approve 一律單步推進到 'approved'。
詳見 services/refund_service.py 模組註解。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import (
    REVIEW_ROLES,
    CurrentUser,
    permission_shadow,
    require_tenant,
    role_required,
)
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    RefundDecision,
    RefundEnvelope,
    RefundRequest,
    RefundRequestCreateRequest,
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
    # CR-0183 補漏（2026-07-27）：本 legacy 端點原僅 require_tenant，而 v2 孿生端點
    # （/tenants/{tid}/refunds）已上 REVIEW_ROLES → 低權限角色改打 legacy 即可繞過。
    # 對齊 v2 與前端 rolePolicy `/admin/refunds`=[admin, operations_manager, reviewer]。
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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


@router.post(
    "/refunds",
    operation_id="createRefundRequest",
    summary="建立退款申請（F-014 dual-trigger）",
    response_model=RefundRequestEnvelope,
)
async def create_refund_request(
    body: RefundRequestCreateRequest,
    response: Response,
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES, fail_closed=True)),
    # CR-0111 shadow：log-only 稽核（矩陣 refunds.write vs 現行 REVIEW_ROLES 守衛），不擋
    _shadow: None = Depends(permission_shadow("refunds", "write")),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    reason_code = (
        body.reason_code.value
        if hasattr(body.reason_code, "value")
        else str(body.reason_code)
    )
    requested_by_role = (
        body.requested_by_role.value
        if hasattr(body.requested_by_role, "value")
        else str(body.requested_by_role)
    )
    refund, created = await refund_service.create_refund_request(
        tenant_id=user.tenant_id,
        work_order_id=str(body.work_order_id),
        amount=body.amount,
        reason=body.reason,
        reason_code=reason_code,
        requested_by_role=requested_by_role,
        requested_by=user.user_id,
        requires_dual_sign=body.requires_dual_sign,
    )
    response.status_code = 201 if created else 200
    payload = {"data": RefundRequest(**refund).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload


@router.get(
    "/refunds/{id}",
    operation_id="getRefundRequest",
    summary="退款申請詳情",
    response_model=RefundRequestEnvelope,
)
async def get_refund_request(
    id: str,
    # CR-0183 補漏（2026-07-27）：同上，對齊 v2 GET /tenants/{tid}/refunds/{id}。
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES, fail_closed=True)),
    # CR-0111 shadow：log-only 稽核（矩陣 refunds.approve vs 現行 REVIEW_ROLES 守衛），不擋
    _shadow: None = Depends(permission_shadow("refunds", "approve")),
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
