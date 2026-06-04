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
from pydantic import BaseModel, Field

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


# ─────────────────────────────────────────────────────────────────────────────
# CR-0009 HD-02=(a) refunds:agent-initiate — single-actor agent 自動退款路徑
#   ADR-0106：LangGraph 特例，不違背全面 SoD 原則（agent 自動化受限於 LLM
#   反應時間，無法即時取得人類 dual-sign；改以 audit log + 金額上限 + 人類
#   後置 review 防護）
# ─────────────────────────────────────────────────────────────────────────────


class _AgentInitiateRefundBody(BaseModel):
    """agent 自動退款請求 body。"""

    work_order_id: str = Field(..., description="工單 UUID")
    amount: str = Field(..., description="退款金額（decimal string）")
    reason: str = Field(..., min_length=1, max_length=500)
    reason_code: str = Field(..., description="退款分類 code（spec ADR-0040）")


@router.post(
    "/tenants/{tenantId}/refunds:agent-initiate",
    operation_id="agentInitiateRefundV2",
    summary="Agent 自動發起退款 v2（CR-0009 HD-02=a single-actor / ADR-0106 LangGraph 特例）",
    status_code=201,
    tags=["M14 Refund"],
)
async def agent_initiate_refund_v2(
    body: _AgentInitiateRefundBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """Agent 服務帳號發起退款 — 不走 SoD dual-sign（HD-02 業主裁，LangGraph 特例）。

    安全控制：
      - actor role 必為 'agent' 或 'system'（人類用戶禁用此 endpoint）
      - 寫入 refunds 表 + audit log（actor_role='agent'）
      - amount 上限由 service 層既有檢查 (NT$100,000 dual-sign threshold)
      - 業主可隨時透過 ops dashboard 後置 review 並 reject
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    if user.role not in {"agent", "system"}:
        raise ApiError(
            "FORBIDDEN",
            "agent-initiate refund requires agent/system service account role",
            403,
        )

    refund, _created = await refund_service.create_refund_request(
        tenant_id=tenantId,
        work_order_id=body.work_order_id,
        amount=body.amount,
        reason=body.reason,
        reason_code=body.reason_code,
        requested_by_role="agent",
        requested_by=user.user_id,
        requires_dual_sign=False,  # HD-02 single-actor
    )

    payload = {"data": RefundRequest(**refund).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201, payload)
    return payload
