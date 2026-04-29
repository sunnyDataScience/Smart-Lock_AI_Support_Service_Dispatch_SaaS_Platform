"""ProblemCards router — 2 read + 4 writes + 1 export。

operationId 對齊 openapi.yaml：
  listProblemCards, getProblemCard, createProblemCard, updateProblemCard,
  confirmProblemCard, resolveProblemCard, exportProblemCard
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    ProblemCard,
    ProblemCardCreateRequest,
    ProblemCardEnvelope,
    ProblemCardExport,
    ProblemCardPage,
    ProblemCardResolveRequest,
    ProblemCardUpdateRequest,
)
from services import problem_card_service

router = APIRouter()


@router.get(
    "/problem-cards",
    operation_id="listProblemCards",
    summary="問題卡列表（cursor 分頁）",
    response_model=ProblemCardPage,
)
async def list_problem_cards(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None, description="過濾特定對話下的問題卡"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await problem_card_service.list_cards(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        conversation_id=conversation_id,
    )
    return {
        "items": [ProblemCard(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/problem-cards/{id}",
    operation_id="getProblemCard",
    summary="問題卡詳情",
    response_model=ProblemCardEnvelope,
)
async def get_problem_card(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    card = await problem_card_service.get_card(
        tenant_id=user.tenant_id, pc_id=id,
    )
    return {"data": ProblemCard(**card).model_dump(mode="json")}


@router.post(
    "/problem-cards",
    operation_id="createProblemCard",
    summary="建立問題卡（每個對話最多一張）",
    status_code=201,
    response_model=ProblemCardEnvelope,
)
async def create_problem_card(
    body: ProblemCardCreateRequest,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    urgency = (
        body.urgency.value
        if body.urgency and hasattr(body.urgency, "value")
        else body.urgency
    )
    door_status = (
        body.door_status.value
        if body.door_status and hasattr(body.door_status, "value")
        else body.door_status
    )
    network_status = (
        body.network_status.value
        if body.network_status and hasattr(body.network_status, "value")
        else body.network_status
    )
    intent = (
        body.intent.value
        if body.intent and hasattr(body.intent, "value")
        else body.intent
    )
    media_urls = (
        [str(u) for u in body.media_urls] if body.media_urls is not None else None
    )
    card = await problem_card_service.create_card(
        tenant_id=user.tenant_id,
        conversation_id=str(body.conversation_id),
        brand=body.brand,
        model=body.model,
        symptom=body.symptom,
        urgency=urgency,
        category=body.category,
        location=body.location,
        door_status=door_status,
        network_status=network_status,
        symptoms=list(body.symptoms) if body.symptoms is not None else None,
        intent=intent,
        media_urls=media_urls,
    )
    payload = {"data": ProblemCard(**card).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.get(
    "/problem-cards/{id}/export",
    operation_id="exportProblemCard",
    summary="匯出問題卡（json / csv / pdf；content 為 base64 編碼）",
    response_model=ProblemCardExport,
)
async def export_problem_card(
    id: str = Path(),
    format: str = Query(default="pdf", pattern="^(pdf|json|csv)$"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await problem_card_service.export_card(
        tenant_id=user.tenant_id, pc_id=id, fmt=format,
    )


@router.patch(
    "/problem-cards/{id}",
    operation_id="updateProblemCard",
    summary="部分更新問題卡（status 變更請走 /confirm 或 /resolve）",
    response_model=ProblemCardEnvelope,
)
async def update_problem_card(
    body: ProblemCardUpdateRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    urgency = body.urgency.value if body.urgency and hasattr(body.urgency, "value") else body.urgency
    status = body.status.value if body.status and hasattr(body.status, "value") else body.status
    media_urls = (
        [str(u) for u in body.media_urls] if body.media_urls is not None else None
    )
    card = await problem_card_service.update_card(
        tenant_id=user.tenant_id,
        pc_id=id,
        brand=body.brand,
        model=body.model,
        symptom=body.symptom,
        category=body.category,
        urgency=urgency,
        status=status,
        media_urls=media_urls,
    )
    return {"data": ProblemCard(**card).model_dump(mode="json")}


@router.post(
    "/problem-cards/{id}/confirm",
    operation_id="confirmProblemCard",
    summary="確認問題卡（draft → confirmed）",
    response_model=ProblemCardEnvelope,
)
async def confirm_problem_card(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    card = await problem_card_service.confirm_card(
        tenant_id=user.tenant_id, pc_id=id,
    )
    payload = {"data": ProblemCard(**card).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/problem-cards/{id}/resolve",
    operation_id="resolveProblemCard",
    summary="結案問題卡（confirmed → resolved）",
    response_model=ProblemCardEnvelope,
)
async def resolve_problem_card(
    body: ProblemCardResolveRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    layer = body.resolution_layer
    layer_str = layer.value if hasattr(layer, "value") else str(layer)
    card = await problem_card_service.resolve_card(
        tenant_id=user.tenant_id,
        pc_id=id,
        resolution_layer=layer_str,
    )
    payload = {"data": ProblemCard(**card).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
