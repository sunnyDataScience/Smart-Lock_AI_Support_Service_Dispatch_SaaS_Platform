"""Refund v2 router — spec-aligned tenant-scoped 退款端點（ADR-0040 v2 / BR-REFUND-006 / FR-0014）。

對齊 frozen spec: saas.refund（三維 SoD + 5-tier）。示範目標架構：
  - tenant-scoped path（非 /api/v1 flat）
  - 三維 SoD headers X-Initiator / X-Approver / X-Executor（require_sod_actors，重用 P1-A）
  - 5-tier 金額分級（伺服器端從 amount 推算，門檻 1k/5k/30k/100k）
  - refund_class 必填 enum + amount > 0
  - config version snapshot + audit linkage

舊 flat 路徑 POST /api/v1/refunds（routers/refunds.py，雙簽 approval_chain 模型）仍保留，
前端遷移後於波次 P2 移除（雙掛過渡，Never break userspace）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import CurrentUser, SodActors, require_sod_actors, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import RefundDecision, RefundRequest, RefundRequestEnvelope
from models.internal import RefundSodEnvelope, RefundSodRequest
from services import config_service, refund_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/refunds",
    operation_id="createRefundSod",
    summary="Create Refund — 三維 SoD + 5-tier (ADR-0040 v2)",
    response_model=RefundSodEnvelope,
)
async def create_refund_sod(
    body: RefundSodRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard：path tenant 必須等於 JWT claim（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    refund_config, config_version = await config_service.get_refund_config(tenantId)

    result = await refund_service.create_refund_sod(
        tenant_id=tenantId,
        work_order_id=body.work_order_id,
        amount=body.amount,
        refund_class=body.refund_class,
        reason=body.reason,
        evidence_ids=body.evidence_ids,
        refund_config=refund_config,
        config_version=config_version,
        sod_initiator=sod.initiator,
        sod_approver=sod.approver,
        sod_executor=sod.executor,
        actor_id=user.user_id,
        actor_role=user.role,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/refunds/{refundId}/decision",
    operation_id="submitRefundDecisionV2",
    summary="Refund Decision — tenant-scoped v2（呼既有 submit_decision，cross-tenant guard）",
    response_model=RefundRequestEnvelope,
)
async def submit_refund_decision_v2(
    body: RefundDecision,
    tenantId: str = Path(...),
    refundId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（對齊 create_refund_sod，ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    decision_str = body.decision.value if hasattr(body.decision, "value") else str(body.decision)

    refund = await refund_service.submit_decision(
        tenant_id=tenantId,
        refund_id=refundId,
        decision=decision_str,
        reason=body.reason,
        decided_by_user_id=user.user_id,
    )

    payload = {"data": RefundRequest(**refund).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.get(
    "/tenants/{tenantId}/refunds/{refundId}",
    operation_id="getRefundSod",
    summary="Get Refund — 三維 SoD + 5-tier (ADR-0040 v2)",
    response_model=RefundSodEnvelope,
)
async def get_refund_sod(
    tenantId: str = Path(...),
    refundId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    result = await refund_service.get_refund_sod(tenant_id=tenantId, refund_id=refundId)
    return {"data": result}
