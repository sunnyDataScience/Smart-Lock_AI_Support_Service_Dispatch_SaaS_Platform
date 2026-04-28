"""Conversations router — 3 endpoints。

operationId 對齊 openapi.yaml：
  listConversations, getConversation, listConversationMessages
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    Conversation,
    ConversationEnvelope,
    ConversationPage,
    ConversationStatus,
    Message,
    MessagePage,
)
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
    user: CurrentUser = Depends(require_tenant),
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


@router.get(
    "/conversations/{id}",
    operation_id="getConversation",
    summary="對話詳情",
    response_model=ConversationEnvelope,
)
async def get_conversation(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
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
    user: CurrentUser = Depends(require_tenant),
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
