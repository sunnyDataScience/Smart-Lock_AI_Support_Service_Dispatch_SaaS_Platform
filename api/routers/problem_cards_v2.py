"""ProblemCards v2 router — tenant-scoped 問題卡端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.1 M03 ProblemCard：
  - GET  /tenants/{tenantId}/problem-cards            → listProblemCardsV2 (cursor 分頁)
  - POST /tenants/{tenantId}/problem-cards            → createProblemCardV2
  - GET  /tenants/{tenantId}/problem-cards/{id}       → getProblemCardV2
  - PATCH /tenants/{tenantId}/problem-cards/{id}      → updateProblemCardV2
  - POST /tenants/{tenantId}/problem-cards/{id}/confirm  → confirmProblemCardV2
  - POST /tenants/{tenantId}/problem-cards/{id}/resolve  → resolveProblemCardV2

NOTE: convert-to-work-order 屬 sync 範疇，留 legacy /api/v1 路由處理（TODO P3）。

舊 flat 路徑 /api/v1/problem-cards（routers/problem_cards.py）仍保留，
加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 problem_card_service 函式，不重寫 SQL
  - envelope：{ data } 對齊既有 ProblemCardEnvelope 慣例
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from fastapi import Response

from models.generated import (
    ConvertProblemCardToWorkOrderRequest,
    ProblemCard,
    ProblemCardCreateRequest,
    ProblemCardEnvelope,
    ProblemCardExport,
    ProblemCardPage,
    ProblemCardResolveRequest,
    ProblemCardUpdateRequest,
    WorkOrder,
    WorkOrderEnvelope,
)
from services import problem_card_service, work_order_service

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/problem-cards",
    operation_id="listProblemCardsV2",
    summary="問題卡列表 v2（tenant-scoped，cursor 分頁）",
    response_model=ProblemCardPage,
    tags=["M03 ProblemCard"],
)
async def list_problem_cards_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None, description="過濾特定對話下的問題卡"),
    status: str | None = Query(default=None, description="狀態（incomplete/complete/resolved 等）"),
    urgency: str | None = Query(default=None, description="緊急度（low/normal/high/critical）"),
    brand: str | None = Query(default=None, description="品牌過濾"),
    created_after: str | None = Query(default=None, description="建立時間下限 ISO 8601"),
    keyword: str | None = Query(default=None, description="關鍵字搜尋（location/brand/model 模糊）"),
    source: str | None = Query(default=None, description="來源過濾（human / ai_line）— CR-0022 AI 草擬佇列"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await problem_card_service.list_cards(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        conversation_id=conversation_id,
        status=status,
        urgency=urgency,
        brand=brand,
        created_after=created_after,
        keyword=keyword,
        source=source,
    )
    return {
        "items": [ProblemCard(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/tenants/{tenantId}/problem-cards",
    operation_id="createProblemCardV2",
    summary="建立問題卡 v2（tenant-scoped；每個對話最多一張）",
    status_code=201,
    response_model=ProblemCardEnvelope,
    tags=["M03 ProblemCard"],
)
async def create_problem_card_v2(
    body: ProblemCardCreateRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

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
        tenant_id=tenantId,
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
    "/tenants/{tenantId}/problem-cards/knowledge-queue",
    operation_id="listKnowledgeQueueV2",
    summary="待補知識佇列（CR-0132/15_SDS §4.6：resolved 但 Gate② 未過的卡）",
    tags=["M03 ProblemCard"],
)
async def list_knowledge_queue_v2(
    tenantId: str = Path(...),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    """精煉服務（15_SDS §9）只汲取 knowledge_ready=true；本佇列列出待補 spine 的卡。"""
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)
    return {"data": await problem_card_service.list_knowledge_queue(tenant_id=tenantId, limit=limit)}


@router.get(
    "/tenants/{tenantId}/problem-cards/{id}",
    operation_id="getProblemCardV2",
    summary="問題卡詳情 v2（tenant-scoped）",
    response_model=ProblemCardEnvelope,
    tags=["M03 ProblemCard"],
)
async def get_problem_card_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    card = await problem_card_service.get_card(
        tenant_id=tenantId, pc_id=id,
    )
    return {"data": ProblemCard(**card).model_dump(mode="json")}


@router.patch(
    "/tenants/{tenantId}/problem-cards/{id}",
    operation_id="updateProblemCardV2",
    summary="部分更新問題卡 v2（tenant-scoped；status 變更請走 /confirm 或 /resolve）",
    response_model=ProblemCardEnvelope,
    tags=["M03 ProblemCard"],
)
async def update_problem_card_v2(
    body: ProblemCardUpdateRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    urgency = body.urgency.value if body.urgency and hasattr(body.urgency, "value") else body.urgency
    status = body.status.value if body.status and hasattr(body.status, "value") else body.status
    media_urls = (
        [str(u) for u in body.media_urls] if body.media_urls is not None else None
    )
    card = await problem_card_service.update_card(
        tenant_id=tenantId,
        pc_id=id,
        brand=body.brand,
        model=body.model,
        symptom=body.symptom,
        category=body.category,
        urgency=urgency,
        status=status,
        media_urls=media_urls,
        emergency_class=body.emergency_class,
        contact_phone=body.contact_phone,
        failure_mode=body.failure_mode,
        triage_tier=body.triage_tier,
        resolution_channel=body.resolution_channel,
        root_cause=body.root_cause,
        root_cause_category=body.root_cause_category,
        corrective_action=body.corrective_action,
        verification=body.verification,
        disposition=body.disposition,
        firmware_version=body.firmware_version,
        serial=body.serial,
    )
    return {"data": ProblemCard(**card).model_dump(mode="json")}


@router.post(
    "/tenants/{tenantId}/problem-cards/{id}/confirm",
    operation_id="confirmProblemCardV2",
    summary="確認問題卡 v2（tenant-scoped；draft → confirmed）",
    response_model=ProblemCardEnvelope,
    tags=["M03 ProblemCard"],
)
async def confirm_problem_card_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    card = await problem_card_service.confirm_card(
        tenant_id=tenantId, pc_id=id,
    )
    payload = {"data": ProblemCard(**card).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/problem-cards/{id}/resolve",
    operation_id="resolveProblemCardV2",
    summary="結案問題卡 v2（tenant-scoped；confirmed → resolved）",
    response_model=ProblemCardEnvelope,
    tags=["M03 ProblemCard"],
)
async def resolve_problem_card_v2(
    body: ProblemCardResolveRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    layer = body.resolution_layer
    layer_str = layer.value if hasattr(layer, "value") else str(layer)
    card = await problem_card_service.resolve_card(
        tenant_id=tenantId,
        pc_id=id,
        resolution_layer=layer_str,
        resolved_by=user.user_id,  # CR-0132：誰解的（Gate② spine）
    )
    payload = {"data": ProblemCard(**card).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# GET :export + POST :convert-to-work-order v2（解 problem-cards/[id] 2 caller）
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/problem-cards/{id}/export",
    operation_id="exportProblemCardV2",
    summary="匯出問題卡 v2（json / csv / pdf；content base64）",
    response_model=ProblemCardExport,
)
async def export_problem_card_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    format: str = Query(default="pdf", pattern="^(pdf|json|csv)$"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await problem_card_service.export_card(
        tenant_id=tenantId, pc_id=id, fmt=format,
    )


@router.post(
    "/tenants/{tenantId}/problem-cards/{id}/convert-to-work-order",
    operation_id="convertProblemCardToWorkOrderV2",
    summary="將已確認問題卡轉為工單 v2（F-002 客服審 PC → 開 WO）",
    response_model=WorkOrderEnvelope,
)
async def convert_problem_card_to_work_order_v2(
    response: Response,
    tenantId: str = Path(...),
    id: str = Path(...),
    body: ConvertProblemCardToWorkOrderRequest | None = None,
    override_reason: str | None = Query(
        default=None,
        description="CR-0042：完整度不足時，admin/ops 帶 reason 可 override 強制轉單",
    ),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    # CR-0042 BR-M03：轉 WO 前完整度 gate（<門檻 → 422，主管帶 reason 可 override）
    await problem_card_service.assert_completeness(
        tenant_id=tenantId,
        pc_id=id,
        customer_address=body.customer_address if body else None,
        actor_role=user.role,
        override_reason=override_reason,
    )
    wo, created = await work_order_service.create_from_problem_card(
        tenant_id=tenantId,
        pc_id=id,
        customer_address=body.customer_address if body else None,
        customer_name=body.customer_name if body else None,
        customer_phone=body.customer_phone if body else None,
        created_by=user.user_id,
    )
    response.status_code = 201 if created else 200
    payload = {"data": WorkOrder(**wo).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload
