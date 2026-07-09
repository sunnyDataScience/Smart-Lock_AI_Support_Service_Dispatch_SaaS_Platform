"""Resolution v2 router — tenant-scoped 解決方案引擎查詢（Track B S6 / CR-0004 §8 C4）。

C4 裁決：問題卡「結案」狀態轉移走 resolveProblemCardV2（problem_cards_v2.py，
confirmed → resolved sub-resource）；本檔提供「解決方案引擎建議」的 tenant-scoped 入口
（FAQ/RAG/escalation 階層串接），供 admin 前端取得 AI 建議解法。

設計原則：
  - 呼既有 resolution_service.resolve_problem（引擎邏輯零重寫；L1 faq_match / L2
    knowledge_base_rag / L3 escalation，純 DB 不直接打 LLM）。
  - require_tenant + cross-tenant guard（ADR-0030）。
  - problemCardId 由 path 帶（取代 legacy flat /resolve 的 body.problem_card_id）。
  - legacy flat POST /api/v1/resolve（resolution.py）雙掛過渡，P4 退場。

MVP 邊界（CR-0004 §8 C4）：引擎「封裝 chatbot-internal」（agent 直呼 service）為 Phase II
純化方向；本波次保留 tenant-scoped REST 入口以維持 admin 前端功能（migration 完整性優先）。
resolution_layer 持久化到 problem_card 留 follow-up（HD-2）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import ResolveResponse
from services import resolution_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/problem-cards/{problemCardId}:resolve-suggest",
    operation_id="resolveProblemSuggestV2",
    summary="解決方案引擎建議 v2（tenant-scoped；FAQ/RAG/escalation 階層）",
    response_model=ResolveResponse,
    tags=["M03 ProblemCard"],
)
async def resolve_problem_suggest_v2(
    tenantId: str = Path(...),
    problemCardId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await resolution_service.resolve_problem(
        tenant_id=tenantId,
        problem_card_id=problemCardId,
    )
    payload = ResolveResponse(**result).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, payload)
    return payload
