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
        "document_number": row[8] if len(row) > 8 else None,
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
    "c.message_count, c.created_at, c.updated_at, c.document_number"
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


async def create_conversation(
    *,
    tenant_id: str,
    line_user_id: str,
    session_id: str,
    display_name: str | None = None,
    channel: str = "line",
) -> tuple[dict, bool]:
    """F-001 ServiceTicket 建立（ADR-009 D pattern bridge）。

    流程:
      1. session_id idempotency check（業務 unique key）→ 既存回 200
      2. line_user_id upsert users 表（ON CONFLICT DO UPDATE last_active_at）
      3. INSERT conversation + 自動 generate document_number (ST-YYYYMMDD-NNNN)
      4. 回 (conversation_dict, created_flag)

    Returns:
        (conv_dict, created_flag): created=True → HTTP 201；created=False → HTTP 200
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. Idempotency check: session_id 是否已存在?
    cur = await db_module._conn.execute(
        "SELECT c.id FROM conversations c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE c.session_id = %s AND u.tenant_id = %s::uuid LIMIT 1",
        (session_id, tenant_id),
    )
    existing = await cur.fetchone()
    if existing:
        conv = await get_conversation(tenant_id=tenant_id, conv_id=str(existing[0]))
        return conv, False

    # 2. Upsert user (line_user_id UNIQUE 約束)
    cur = await db_module._conn.execute(
        "INSERT INTO users (line_user_id, display_name, tenant_id, role, last_active_at) "
        "VALUES (%s, %s, %s::uuid, 'line_user', NOW()) "
        "ON CONFLICT (line_user_id) DO UPDATE SET "
        "  display_name = COALESCE(EXCLUDED.display_name, users.display_name), "
        "  last_active_at = NOW() "
        "RETURNING id",
        (line_user_id, display_name, tenant_id),
    )
    user_row = await cur.fetchone()
    if not user_row:
        raise ApiError("INTERNAL_ERROR", "Failed to upsert user", 500)
    user_id = str(user_row[0])

    # 3. INSERT conversation + 自動 doc number
    cur = await db_module._conn.execute(
        "INSERT INTO conversations "
        "  (user_id, session_id, status, document_number) "
        "VALUES (%s::uuid, %s, 'active', generate_doc_number('ST', 'doc_seq_st')) "
        "RETURNING id",
        (user_id, session_id),
    )
    new_row = await cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert conversation", 500)
    new_conv_id = str(new_row[0])

    conv = await get_conversation(tenant_id=tenant_id, conv_id=new_conv_id)
    return conv, True


async def _append_message(
    *, conv_id: str, role: str, content: str, sender_role: str
) -> None:
    """內部 helper：寫一則 message（content_type=text）。空字串不寫。"""
    if not (content or "").strip():
        return
    metadata = {"sender_role": sender_role}
    await db_module._conn.execute(
        "INSERT INTO messages (conversation_id, role, content_type, content, metadata) "
        "VALUES (%s::uuid, %s, 'text', %s, %s::jsonb)",
        (conv_id, role, content, json.dumps(metadata)),
    )


async def ingest_turn(
    *,
    tenant_id: str,
    line_user_id: str,
    session_id: str,
    user_text: str = "",
    assistant_text: str = "",
    display_name: str | None = None,
) -> dict:
    """旁路持久化一輪 LINE 對話（方案 A，由 agent gateway 經 internal token 呼叫）。

    流程：
      1. ensure conversation（復用 create_conversation 的 session_id 冪等 upsert）
      2. append 客人訊息（role='user'，metadata.sender_role='line_user'）
      3. append AI 回覆（role='assistant'，metadata.sender_role='ai'）
      4. message_count += 實際寫入則數（空字串不計）
      5. 回 {conversation_id, messages_appended}

    與 send_message 的差異：send_message 是「客服人工接管」且要求 escalated 狀態並
    觸發 LINE push；ingest_turn 是「AI 自動對話流水帳」，不限狀態、不 push（訊息
    本來就已由 gateway 回給客人）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    conv, _created = await create_conversation(
        tenant_id=tenant_id,
        line_user_id=line_user_id,
        session_id=session_id,
        display_name=display_name,
    )
    conv_id = conv["id"]

    appended = 0
    if (user_text or "").strip():
        await _append_message(
            conv_id=conv_id, role="user", content=user_text, sender_role="line_user"
        )
        appended += 1
    if (assistant_text or "").strip():
        await _append_message(
            conv_id=conv_id, role="assistant", content=assistant_text, sender_role="ai"
        )
        appended += 1

    if appended:
        await db_module._conn.execute(
            "UPDATE conversations SET message_count = message_count + %s "
            "WHERE id = %s::uuid",
            (appended, conv_id),
        )

    return {"conversation_id": conv_id, "messages_appended": appended}


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
      5. 呼叫 LINE Push API 將訊息推給 line_user_id（fail-soft，由 line_push_service 處理）
      6. TODO: 寫 audit log（line_push_service 已自帶 audit；handover 專屬 audit 待補）
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

    # 5. LINE Push（F-018 closeout）— fail-soft；推送失敗不阻斷客服訊息寫入
    if line_user_id:
        try:
            from services import line_push_service

            await line_push_service.push_text(
                line_user_id=line_user_id,
                text=content,
                actor_user_id=sender_user_id,
                tenant_id=tenant_id,
            )
        except Exception:  # noqa: BLE001 — must never break handover write
            logger.warning(
                "LINE push failed during handover (conv=%s)", conv_id, exc_info=True
            )
    else:
        logger.info(
            "LINE push skipped (no line_user_id): conv=%s sender=%s",
            conv_id,
            sender_user_id,
        )

    # 6. TODO: audit log（寫入 audit_logs 表，標 actor=sender_user_id、
    #    action=send_handover_message、entity=message:<id>）

    return _msg_row_to_dict(msg_row)


async def resolve_handover(*, tenant_id: str, conv_id: str) -> dict:
    """結束接管 / 交還 AI：對話 escalated → active（CR-0024 Phase 1，D3）。

    流程：
      1. tenant 隔離 + 撈狀態（404 if 不屬該 tenant）
      2. 非 escalated → 409（無接管可結束，避免誤翻其他狀態）
      3. UPDATE conversations.status='active'（AI 接手），回更新後 conversation dict

    交還後 agent gateway 下次查 handover-state 得 escalated=false → AI 恢復正常接待。
    冪等性由呼叫端語意保證（已 active 再呼叫會收 409，符合「沒有接管可結束」）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT c.status FROM conversations c JOIN users u ON c.user_id = u.id "
        "WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
        (conv_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Conversation not found", 404)
    if row[0] not in _HANDOVER_ALLOWED_DB_STATUSES:
        raise ApiError(
            "CONVERSATION_NOT_ESCALATED",
            f"Conversation is not under human handover (current DB status: {row[0]})",
            409,
        )

    await db_module._conn.execute(
        "UPDATE conversations SET status = 'active', updated_at = NOW() "
        "WHERE id = %s::uuid",
        (conv_id,),
    )
    return await get_conversation(tenant_id=tenant_id, conv_id=conv_id)


async def get_handover_state(*, tenant_id: str, session_id: str) -> dict:
    """供 agent gateway 查某對話是否處於人工接管中（CR-0024 Phase 1）。

    以 session_id（= conversation external 冪等鍵）定位對話，回
    {escalated: bool, reason: str|None}。reason 取該對話最新 AI 草擬問題卡的
    症狀摘要（Phase 2 relatedness 分類會用到；Phase 1 gateway 只看 escalated）。
    查無對話 → escalated=false（agent 照常回，fail-soft 友善預設）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT c.id, c.status FROM conversations c JOIN users u ON c.user_id = u.id "
        "WHERE c.session_id = %s AND u.tenant_id = %s::uuid LIMIT 1",
        (session_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        return {"escalated": False, "reason": None}

    conv_id, status = row[0], row[1]
    escalated = status in _HANDOVER_ALLOWED_DB_STATUSES
    reason: str | None = None
    if escalated:
        pc_cur = await db_module._conn.execute(
            "SELECT symptoms FROM problem_cards WHERE conversation_id = %s::uuid "
            "ORDER BY updated_at DESC LIMIT 1",
            (conv_id,),
        )
        pc_row = await pc_cur.fetchone()
        if pc_row and isinstance(pc_row[0], list) and pc_row[0]:
            reason = str(pc_row[0][-1])[:500]
    return {"escalated": escalated, "reason": reason}
