"""Resolution router — resolveProblem 端點。

operationId 對齊 openapi.yaml：resolveProblem (POST /resolve)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import ResolveRequest, ResolveResponse
from services import resolution_service

router = APIRouter()


@router.post(
    "/resolve",
    operation_id="resolveProblem",
    summary="解決方案引擎（FAQ/RAG/LLM/Escalation 階層串接）",
    response_model=ResolveResponse,
)
async def resolve_problem(
    body: ResolveRequest,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    result = await resolution_service.resolve_problem(
        tenant_id=user.tenant_id,
        problem_card_id=str(body.problem_card_id),
    )
    payload = ResolveResponse(**result).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, payload)
    return payload
