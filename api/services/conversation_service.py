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
