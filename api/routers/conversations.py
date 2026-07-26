"""Conversations router — 5 endpoints。

operationId 對齊 openapi.yaml：
  listConversations, getConversation, createConversation,
  listConversationMessages, sendChatMessage
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
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


@router.get(
    "/conversations",
    operation_id="listConversations",
    summary="對話列表（cursor 分頁）",
    response_model=ConversationPage,
)
async def list_conversations(
    status: ConversationStatus | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    # CR-0183 補漏（2026-07-27）：v2 孿生端點已上守衛、本 legacy 端點漏掛，
    # 兩者皆掛載 → 低權限角色改打 legacy 路徑即可繞過。對齊 v2 守衛。
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    page = await conversation_service.list_conversations(
        tenant_id=user.tenant_id,
        status=status.value if status else None,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [Conversation(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/conversations",
    operation_id="createConversation",
    summary="建立對話（F-001 LINE 報修首訊建 ServiceTicket）",
    response_model=ConversationEnvelope,
)
async def create_conversation(
    body: ConversationCreateRequest,
    response: Response,
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    channel = (
        body.channel.value if hasattr(body.channel, "value") else str(body.channel)
    )
    conv, created = await conversation_service.create_conversation(
        tenant_id=user.tenant_id,
        line_user_id=body.line_user_id,
        session_id=body.session_id,
        display_name=body.display_name,
        channel=channel,
    )
    response.status_code = 201 if created else 200
    payload = {"data": Conversation(**conv).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload


@router.get(
    "/conversations/{id}",
    operation_id="getConversation",
    summary="對話詳情",
    response_model=ConversationEnvelope,
)
async def get_conversation(
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    conv = await conversation_service.get_conversation(
        tenant_id=user.tenant_id, conv_id=id,
    )
    return {"data": Conversation(**conv).model_dump(mode="json")}


@router.get(
    "/conversations/{id}/messages",
    operation_id="listConversationMessages",
    summary="對話訊息列表（cursor 分頁）",
    response_model=MessagePage,
)
async def list_conversation_messages(
    id: str = Path(),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    # CR-0183 補漏（2026-07-27）：v2 孿生端點已上守衛、本 legacy 端點漏掛，
    # 兩者皆掛載 → 低權限角色改打 legacy 路徑即可繞過。對齊 v2 守衛。
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
) -> dict:
    page = await conversation_service.list_messages(
        tenant_id=user.tenant_id,
        conv_id=id,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [Message(**m).model_dump(mode="json") for m in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/conversations/{id}/messages",
    operation_id="sendChatMessage",
    summary="發送訊息（人類客服接管後使用）",
    response_model=Message,
    status_code=201,
)
async def send_chat_message(
    body: SendChatMessageRequest,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """客服接管 escalated 對話後送訊息給 LINE 用戶。

    僅允許 admin / customer_service 角色（其他角色 → 403）。
    """
    # RBAC：客服 / 主管才能接管發訊
    if user.role not in {"admin", "customer_service", "manager", "supervisor"}:
        from core.errors import ApiError
        raise ApiError(
            "FORBIDDEN",
            "Only customer service or supervisor roles can send takeover messages",
            403,
        )

    msg = await conversation_service.send_message(
        tenant_id=user.tenant_id,
        conv_id=id,
        sender_user_id=user.user_id,
        content=body.content,
        media_uri=str(body.media_uri) if body.media_uri else None,
    )
    payload = Message(**msg).model_dump(mode="json")
    if idem is not None:
        await idem.save(201, payload)
    return payload
