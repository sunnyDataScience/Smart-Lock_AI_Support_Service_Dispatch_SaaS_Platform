"""Notifications 業務邏輯。

不做真正的推播 channel（push email/SMS/LINE）；僅寫入 notifications 表，
由前端 polling 或未來的 SSE/WebSocket consumer 拉取顯示。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.notification_service")


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "type": row[1],
        "severity": row[2],
        "title": row[3],
        "body": row[4],
        "source": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
        "read_at": row[7].isoformat() if row[7] else None,
        "archived_at": row[8].isoformat() if row[8] else None,
        "related_entity": row[9],
        "actions": row[10] or [],
        "raw_event_id": str(row[11]) if row[11] else None,
    }


async def list_notifications(
    *,
    tenant_id: str,
    user_id: str,
    cursor: str | None,
    limit: int,
    status: str | None,
    types: list[str] | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "user_id = %s::uuid"]
    args: list = [tenant_id, user_id]

    if status == "unread":
        where.append("read_at IS NULL AND archived_at IS NULL")
    elif status == "read":
        where.append("read_at IS NOT NULL AND archived_at IS NULL")
    elif status == "archived":
        where.append("archived_at IS NOT NULL")
    # status='all' or None → no filter

    if types:
        placeholders = ",".join(["%s"] * len(types))
        where.append(f"type IN ({placeholders})")
        args.extend(types)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        "SELECT id, type, severity, title, body, source, created_at, read_at, "
        "archived_at, related_entity, actions, raw_event_id "
        "FROM notifications "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def update_notification(
    *, tenant_id: str, user_id: str, notification_id: str,
    read_at: datetime | None, archived_at: datetime | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sets = []
    args: list = []
    if read_at is not None:
        sets.append("read_at = %s")
        args.append(read_at)
    elif read_at is None and "read_at" in (read_at,):  # explicit null clears
        sets.append("read_at = NULL")
    if archived_at is not None:
        sets.append("archived_at = %s")
        args.append(archived_at)

    if not sets:
        # 沒任何欄位變動
        cur = await db_module._conn.execute(
            "SELECT id, type, severity, title, body, source, created_at, read_at, archived_at, related_entity, actions, raw_event_id "
            "FROM notifications WHERE id = %s::uuid AND tenant_id = %s::uuid AND user_id = %s::uuid",
            (notification_id, tenant_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", "Notification not found", 404)
        return _row_to_dict(row)

    args.extend([notification_id, tenant_id, user_id])
    sql = (
        f"UPDATE notifications SET {', '.join(sets)} "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND user_id = %s::uuid "
        "RETURNING id, type, severity, title, body, source, created_at, read_at, archived_at, related_entity, actions, raw_event_id"
    )
    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Notification not found", 404)
    return _row_to_dict(row)


async def bulk_action(
    *, tenant_id: str, user_id: str, ids: list[str], action: str,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if len(ids) > 1000:
        raise ApiError(
            "NOTIFICATION_BULK_LIMIT_EXCEEDED",
            "Bulk action accepts at most 1000 ids",
            422,
        )
    if not ids:
        return {"affected": 0}

    placeholders = ",".join(["%s::uuid"] * len(ids))
    args: list = list(ids)

    if action == "mark_read":
        sql = (
            f"UPDATE notifications SET read_at = NOW() "
            f"WHERE id IN ({placeholders}) "
            f"AND tenant_id = %s::uuid AND user_id = %s::uuid AND read_at IS NULL"
        )
    elif action == "mark_unread":
        sql = (
            f"UPDATE notifications SET read_at = NULL "
            f"WHERE id IN ({placeholders}) "
            f"AND tenant_id = %s::uuid AND user_id = %s::uuid"
        )
    elif action == "archive":
        sql = (
            f"UPDATE notifications SET archived_at = NOW() "
            f"WHERE id IN ({placeholders}) "
            f"AND tenant_id = %s::uuid AND user_id = %s::uuid AND archived_at IS NULL"
        )
    elif action == "delete":
        sql = (
            f"DELETE FROM notifications "
            f"WHERE id IN ({placeholders}) "
            f"AND tenant_id = %s::uuid AND user_id = %s::uuid"
        )
    else:
        raise ApiError("VALIDATION_ERROR", f"Unknown action: {action}", 422)

    args.extend([tenant_id, user_id])
    cur = await db_module._conn.execute(sql, args)
    return {"affected": cur.rowcount}


async def mark_all_read(
    *, tenant_id: str, user_id: str, type_filter: list[str] | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "user_id = %s::uuid", "read_at IS NULL", "severity != 'critical'"]
    args: list = [tenant_id, user_id]
    if type_filter:
        placeholders = ",".join(["%s"] * len(type_filter))
        where.append(f"type IN ({placeholders})")
        args.extend(type_filter)

    sql = f"UPDATE notifications SET read_at = NOW() WHERE {' AND '.join(where)}"
    cur = await db_module._conn.execute(sql, args)
    return {"affected": cur.rowcount}


async def push_notification(req: dict, *, tenant_id: str) -> dict:
    """target_type='user': target_id 即 users.id；其他 target type Phase 1 暫不展開。

    UAT-0718 W5-2（已釘契約）：寫 DB 後 publish 到既有 WS hub
    /realtime/notifications/{user_id}（payload=通知 JSON）——前端鈴鐺訂閱該
    WS，收到訊息 refreshBadge。fail-soft：publish 失敗不影響通知落庫。
    UAT-0718 W5-3：可選 related_entity（jsonb）讓通知帶可點跳轉。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    target_type = req.get("target_type")
    target_id = str(req["target_id"])

    if target_type != "user":
        raise ApiError(
            "NOT_IMPLEMENTED",
            f"target_type={target_type} not supported in Phase 1 (only 'user')",
            422,
        )

    related_entity = req.get("related_entity")

    notif_id = str(uuid.uuid4())
    cur = await db_module._conn.execute(
        "INSERT INTO notifications (id, tenant_id, user_id, type, severity, title, body, source, related_entity) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'info', %s, %s, 'system', %s::jsonb) "
        "RETURNING id, type, severity, title, body, source, created_at, read_at, archived_at, related_entity, actions, raw_event_id",
        (
            notif_id, tenant_id, target_id, req["type"], req["title"], req.get("body", ""),
            json.dumps(related_entity, ensure_ascii=False) if related_entity else None,
        ),
    )
    row = await cur.fetchone()
    notif = _row_to_dict(row)

    # 即時推播（fail-soft：WS 掛掉不影響已落庫的通知，前端 polling 仍拿得到）
    try:
        from realtime.ws_hub import hub  # 延遲 import 避免循環

        await hub.publish(
            f"/realtime/notifications/{target_id}",
            {"type": "notification", "payload": notif},
        )
    except Exception:  # noqa: BLE001
        logger.exception("notification ws publish failed (non-fatal): %s", notif_id[:8])
    return notif
