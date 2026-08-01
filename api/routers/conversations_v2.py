"""Conversations v2 router — tenant-scoped 對話端點（CR-0003 P2-W2 / FR-0018）。

對齊 frozen spec §FR-0018 M01 Conversation：
  - GET  /tenants/{tenantId}/conversations                 → listConversations
  - POST /tenants/{tenantId}/conversations                 → createConversation
  - GET  /tenants/{tenantId}/conversations/{id}            → getConversation
  - GET  /tenants/{tenantId}/conversations/{id}/messages   → listConversationMessages
  - POST /tenants/{tenantId}/conversations/{id}/messages   → sendChatMessage

舊 flat 路徑 /api/v1/conversations（routers/conversations.py）仍保留，
加掛 Deprecation header（D3 DeprecationMiddleware）雙掛過渡；前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 conversation_service 函式，不重寫 SQL
  - POST 用 idempotency_guard（POST createConversation + sendChatMessage）
  - W1 教訓：不直接用 generated response_model 嚴格驗證 service 輸出；
    改以寬鬆 dict + Pydantic model 轉換 before 回傳，避免 float/None mismatch
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    Conversation,
    ConversationCreateRequest,
    ConversationEnvelope,
    ConversationPage,
    ConversationStatus,
    Message,
    MessagePage,
)
from models.internal import SendChatMessageRequest
from services import conversation_service

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/conversations — tenant-scoped list
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/conversations",
    operation_id="listConversationsV2",
    summary="對話列表 v2（tenant-scoped，cursor 分頁）",
    response_model=ConversationPage,
    tags=["Conversations"],
)
async def list_conversations_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    status: ConversationStatus | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await conversation_service.list_conversations(
        tenant_id=tenantId,
        status=status.value if status else None,
        cursor=cursor,
        limit=limit,
    )
    # W1 教訓：model_dump 後回傳，避免 generated model 嚴格 pattern 卡住
    return {
        "items": [_safe_conv(c) for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/conversations — create conversation
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/conversations",
    operation_id="createConversationV2",
    summary="建立對話 v2（tenant-scoped，F-001 LINE 報修首訊建 ServiceTicket）",
    response_model=ConversationEnvelope,
    tags=["Conversations"],
)
async def create_conversation_v2(
    body: ConversationCreateRequest,
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    response: Response = None,
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

    channel = (
        body.channel.value if hasattr(body.channel, "value") else str(body.channel)
    )
    conv, created = await conversation_service.create_conversation(
        tenant_id=tenantId,
        line_user_id=body.line_user_id,
        session_id=body.session_id,
        display_name=body.display_name,
        channel=channel,
    )
    if response is not None:
        response.status_code = 201 if created else 200
    payload = {"data": _safe_conv(conv)}
    if idem is not None:
        await idem.save(201 if created else 200, payload)
    return payload


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/conversations/{id} — conversation detail
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/conversations/{id}",
    operation_id="getConversationV2",
    summary="對話詳情 v2（tenant-scoped）",
    response_model=ConversationEnvelope,
    tags=["Conversations"],
)
async def get_conversation_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    id: str = Path(..., description="對話 UUID"),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    conv = await conversation_service.get_conversation(
        tenant_id=tenantId, conv_id=id,
    )
    return {"data": _safe_conv(conv)}


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/conversations/{id}/messages — message list
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/conversations/{id}/messages",
    operation_id="listConversationMessagesV2",
    summary="對話訊息列表 v2（tenant-scoped，cursor 分頁）",
    response_model=MessagePage,
    tags=["Conversations"],
)
async def list_conversation_messages_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    id: str = Path(..., description="對話 UUID"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await conversation_service.list_messages(
        tenant_id=tenantId,
        conv_id=id,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [_safe_msg(m) for m in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/conversations/{id}/messages — send message (handover)
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/conversations/{id}/messages",
    operation_id="sendChatMessageV2",
    summary="發送訊息 v2（tenant-scoped，人類客服接管後使用）",
    response_model=Message,
    status_code=201,
    tags=["Conversations"],
)
async def send_chat_message_v2(
    body: SendChatMessageRequest,
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    id: str = Path(..., description="對話 UUID"),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """客服接管 escalated 對話後送訊息給 LINE 用戶 v2（tenant-scoped）。

    僅允許 admin / customer_service 角色（其他角色 → 403）。
    """
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # RBAC：客服 / 主管才能接管發訊
    if user.role not in {"admin", "customer_service", "manager", "supervisor"}:
        raise ApiError(
            "FORBIDDEN",
            "Only customer service or supervisor roles can send takeover messages",
            403,
        )

    msg = await conversation_service.send_message(
        tenant_id=tenantId,
        conv_id=id,
        sender_user_id=user.user_id,
        content=body.content,
        media_uri=str(body.media_uri) if body.media_uri else None,
    )
    payload = _safe_msg(msg)
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/conversations/{id}/request-handover",
    operation_id="requestConversationHandover",
    summary="客服手動接管對話（active → escalated）",
    response_model=Conversation,
    tags=["Conversations"],
)
async def request_conversation_handover_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    id: str = Path(..., description="對話 UUID"),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    """客服主動接管對話（status active → escalated），與 resolve-handover 互為鏡像。

    **為什麼要有這支**：在此之前全系統只有 AI 那條路會把對話翻成 escalated
    （transfer_to_human → escalation ingest → problem_card_service:952）。AI 那條路
    一旦沒走成，客服在 UI 上**零復原手段**——發訊框開關是 status==="waiting_human"
    嚴格比對，狀態沒翻就誰都回不了那位客人的 LINE，對話也結不掉。
    業主 2026-08-01 即因此卡住。

    權限比照 resolve-handover：僅 admin / customer_service / manager / supervisor。
    已在接管中 → 409（呼叫端要能分辨「我翻的」與「本來就翻了」）。
    非 active（已結案等）→ 409，避免誤翻已結束的對話。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    if user.role not in {"admin", "customer_service", "manager", "supervisor"}:
        raise ApiError(
            "FORBIDDEN",
            "Only customer service or supervisor roles can request handover",
            403,
        )

    conv = await conversation_service.request_handover(
        tenant_id=tenantId, conv_id=id, actor_id=user.user_id, actor_role=user.role,
    )
    return _safe_conv(conv)


@router.post(
    "/tenants/{tenantId}/conversations/{id}/resolve-handover",
    operation_id="resolveConversationHandover",
    summary="結束接管 / 交還 AI（CR-0024，escalated → active）",
    response_model=Conversation,
    tags=["Conversations"],
)
async def resolve_conversation_handover_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    id: str = Path(..., description="對話 UUID"),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    """客服結束人工接管，把對話交還 AI（status escalated → active）。

    僅 admin / customer_service / manager / supervisor 可操作（其他 → 403）。
    非 escalated → 409（沒有接管可結束）。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    if user.role not in {"admin", "customer_service", "manager", "supervisor"}:
        raise ApiError(
            "FORBIDDEN",
            "Only customer service or supervisor roles can resolve handover",
            403,
        )

    # 2026-08-02：帶 actor 進去留痕——事故追查時「誰把客人從真人手上拿回給 AI」
    # 原本只能靠會過期的 Cloud Run request log 才查得到。
    conv = await conversation_service.resolve_handover(
        tenant_id=tenantId, conv_id=id, actor_id=user.user_id, actor_role=user.role,
    )
    return _safe_conv(conv)


# ---------------------------------------------------------------------------
# Private helpers — W1 教訓：寬鬆 model_dump 避免嚴格 pattern 卡住
# ---------------------------------------------------------------------------


def _safe_conv(raw: dict) -> dict:
    """將 conversation_service 回傳的 raw dict 套進 Conversation model 再 dump。

    W1 教訓：service 輸出的 field 型別（resolution_layer Enum / None 等）
    可能與 generated.Conversation 嚴格 pattern 不完全相符；透過 model 轉換
    確保欄位合法，再以 mode='json' dump 輸出可序列化的 dict。
    """
    return Conversation(**raw).model_dump(mode="json")


def _safe_msg(raw: dict) -> dict:
    """將 message_service 回傳的 raw dict 套進 Message model 再 dump。"""
    return Message(**raw).model_dump(mode="json")
