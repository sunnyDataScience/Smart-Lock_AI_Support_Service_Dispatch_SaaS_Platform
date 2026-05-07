"""Conversations 業務邏輯。

讀 conversations + users + messages 表，mapping 成 OpenAPI schema：
  - conversations.status (active/collecting/resolving/resolved/escalated/expired)
    → ConversationStatus (active/waiting_human/closed)
  - conversations.resolution_layer (L1/L2/L3)
    → ResolutionLayer (case_library/rag/human/null)
  - messages.content_type (text/image/location/flex) → MessageType (fallback text)
  - messages.metadata.image_url → media_url

租戶隔離：透過 users.tenant_id JOIN（conversations 表本身無 tenant_id）。
"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.conversation_service")


_VALID_STATUSES = {"active", "waiting_human", "closed"}

_DB_STATUS_TO_API = {
    "active": "active",
    "collecting": "active",
    "resolving": "active",
    "escalated": "waiting_human",
    "resolved": "closed",
    "expired": "closed",
}

_DB_RESOLUTION_TO_API = {
    "L1": "case_library",
    "L2": "rag",
    "L3": "human",
}

_VALID_MESSAGE_TYPES = {"text", "image", "audio", "video", "sticker"}


def _api_status_to_db(status: str) -> list[str]:
    """OpenAPI ConversationStatus → DB status values (反向映射)。"""
    matches = [db for db, api in _DB_STATUS_TO_API.items() if api == status]
    return matches or [status]


def _coerce_status(db_status: str | None) -> str:
    if not db_status:
        return "active"
    if db_status in _VALID_STATUSES:
        return db_status
    return _DB_STATUS_TO_API.get(db_status, "active")


def _coerce_resolution(db_layer: str | None) -> str | None:
    if not db_layer:
        return None
    return _DB_RESOLUTION_TO_API.get(db_layer)


def _coerce_message_type(db_type: str | None) -> str:
    if not db_type:
        return "text"
    if db_type in _VALID_MESSAGE_TYPES:
        return db_type
    return "text"


def _conv_row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "line_user_id": row[1] or "",
        "display_name": row[2] or "",
        "status": _coerce_status(row[3]),
        "resolution_layer": _coerce_resolution(row[4]),
        "message_count": int(row[5] or 0),
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


def _msg_row_to_dict(row: tuple) -> dict:
    metadata = row[5] or {}
    media_url = None
    if isinstance(metadata, dict):
        media_url = metadata.get("image_url") or metadata.get("media_url")
    return {
        "id": str(row[0]),
        "conversation_id": str(row[1]),
        "role": row[2] or "system",
        "type": _coerce_message_type(row[3]),
        "content": row[4] or "",
        "media_url": media_url,
        "created_at": row[6].isoformat() if row[6] else None,
    }


_CONV_SELECT = (
    "c.id, u.line_user_id, u.display_name, c.status, c.resolution_layer, "
    "c.message_count, c.created_at, c.updated_at"
)


async def list_conversations(
    *,
    tenant_id: str,
    status: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        db_statuses = _api_status_to_db(status)
        placeholders = ", ".join(["%s"] * len(db_statuses))
        where.append(f"c.status IN ({placeholders})")
        args.extend(db_statuses)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(c.created_at, c.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_CONV_SELECT} "
        f"FROM conversations c JOIN users u ON c.user_id = u.id "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY c.created_at DESC, c.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_conv_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_conversation(*, tenant_id: str, conv_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_CONV_SELECT} "
        f"FROM conversations c JOIN users u ON c.user_id = u.id "
        f"WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
        (conv_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Conversation not found", 404)
    return _conv_row_to_dict(row)


async def list_messages(
    *,
    tenant_id: str,
    conv_id: str,
    cursor: str | None,
    limit: int,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 先驗證 conversation 屬於 tenant（確保 404 而非空陣列）
    own_cur = await db_module._conn.execute(
        "SELECT 1 FROM conversations c JOIN users u ON c.user_id = u.id "
        "WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
        (conv_id, tenant_id),
    )
    if not await own_cur.fetchone():
        raise ApiError("NOT_FOUND", "Conversation not found", 404)

    where = ["conversation_id = %s::uuid"]
    args: list = [conv_id]

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        "SELECT id, conversation_id, role, content_type, content, metadata, created_at "
        "FROM messages "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_msg_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# Conversation DB statuses that allow human agent to send a takeover message.
# 對應 OpenAPI ConversationStatus="waiting_human"（DB 上是 "escalated"）。
_HANDOVER_ALLOWED_DB_STATUSES = {"escalated"}


async def send_message(
    *,
    tenant_id: str,
    conv_id: str,
    sender_user_id: str,
    content: str,
    media_uri: str | None = None,
) -> dict:
    """客服接管後寫入訊息 + 觸發 LINE Push（push 部分待 wire）。

    流程：
      1. 驗證 conversation 屬於 tenant 並抓 line_user_id + status
      2. 檢查 status 必須是 escalated（OpenAPI: waiting_human）
      3. INSERT messages，role='assistant'（LINE 視角），
         metadata 標 sender_role=agent_human + sender_id 供稽核
      4. UPDATE conversations.message_count + updated_at
      5. TODO: 呼叫 LINE Push API 將訊息推給 line_user_id
      6. TODO: 寫 audit log
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. tenant 隔離 + 撈狀態 + LINE user id
    cur = await db_module._conn.execute(
        "SELECT c.status, u.line_user_id "
        "FROM conversations c JOIN users u ON c.user_id = u.id "
        "WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
        (conv_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Conversation not found", 404)

    db_status, line_user_id = row[0], row[1]

    # 2. 接管狀態檢查
    if db_status not in _HANDOVER_ALLOWED_DB_STATUSES:
        raise ApiError(
            "CONVERSATION_NOT_ESCALATED",
            f"Conversation must be in waiting_human state to send agent message "
            f"(current DB status: {db_status})",
            409,
        )

    # 3. INSERT message — role 用 'assistant'（對 LINE user 而言是「客服回覆」），
    #    metadata 標 sender_role=agent_human + sender_id 供 audit / UI 區分
    metadata = {
        "sender_role": "agent_human",
        "sender_id": sender_user_id,
    }
    if media_uri:
        metadata["media_url"] = media_uri

    insert_cur = await db_module._conn.execute(
        "INSERT INTO messages (conversation_id, role, content_type, content, metadata) "
        "VALUES (%s::uuid, %s, %s, %s, %s::jsonb) "
        "RETURNING id, conversation_id, role, content_type, content, metadata, created_at",
        (
            conv_id,
            "assistant",
            "text",
            content,
            json.dumps(metadata),
        ),
    )
    msg_row = await insert_cur.fetchone()
    if not msg_row:
        raise ApiError("DB_ERROR", "Failed to insert message", 500)

    # 4. 更新 conversation message_count（updated_at 由 trigger 處理）
    await db_module._conn.execute(
        "UPDATE conversations SET message_count = message_count + 1 "
        "WHERE id = %s::uuid",
        (conv_id,),
    )

    # 5. TODO: integrate LINE Push API
    #    需呼叫 line-bot-sdk 的 push_message(line_user_id, content)，
    #    或透過 message broker 投到 agent 服務統一推播。
    #    目前先 log 供開發追蹤。
    logger.info(
        "TODO LINE Push: conv=%s line_user=%s sender=%s content_len=%d",
        conv_id,
        line_user_id,
        sender_user_id,
        len(content),
    )

    # 6. TODO: audit log（寫入 audit_logs 表，標 actor=sender_user_id、
    #    action=send_handover_message、entity=message:<id>）

    return _msg_row_to_dict(msg_row)
