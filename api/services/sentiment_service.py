"""Sentiment Alerts 業務邏輯。

範圍：listSentimentAlerts + updateSentimentAlert（status / admin_note 變更）。
不含：觸發告警寫入（由 agent 端 sentiment 偵測模組接入）。

狀態機：pending → acknowledged → resolved（單向，不允許回退）。
        pending → resolved 也允許（後台直接結案不經 acknowledged）。

租戶隔離：sentiment_alerts 沒有 tenant_id，透過
    JOIN conversations c JOIN users u ON c.user_id = u.id
    WHERE u.tenant_id = %s
與 problem_card_service / work_order_service 同 pattern。
"""

from __future__ import annotations

import logging
from datetime import datetime

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.sentiment_service")


_VALID_STATUSES = ("pending", "acknowledged", "resolved")

# 狀態機白名單（只允許單向前進，不允許回退）
_STATUS_TRANSITIONS = {
    "pending": {"acknowledged", "resolved"},
    "acknowledged": {"resolved"},
    "resolved": set(),
}


_SELECT_COLUMNS = (
    "sa.id, sa.conversation_id, sa.consumer_message, "
    "sa.sentiment_label, sa.confidence, "
    "COALESCE(sa.detected_keywords, ARRAY[]::text[]) AS detected_keywords, "
    "sa.problem_card_id, sa.status, "
    "COALESCE(sa.notified_admin_ids, ARRAY[]::uuid[]) AS notified_admin_ids, "
    "sa.admin_note, sa.created_at"
)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "conversation_id": str(row[1]),
        "consumer_message": row[2] or "",
        "sentiment_label": row[3],
        "confidence": float(row[4]) if row[4] is not None else 0.0,
        "detected_keywords": list(row[5] or []),
        "problem_card_id": str(row[6]) if row[6] else None,
        "status": row[7],
        "notified_admin_ids": [str(x) for x in (row[8] or [])],
        "admin_note": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
    }


async def list_alerts(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None,
    start_time: datetime | None,
) -> dict:
    if status is not None and status not in _VALID_STATUSES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"invalid status '{status}'; expected one of {_VALID_STATUSES}",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status is not None:
        where.append("sa.status = %s")
        args.append(status)

    if start_time is not None:
        where.append("sa.created_at >= %s")
        args.append(start_time)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(sa.created_at, sa.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM sentiment_alerts sa "
        f"JOIN conversations c ON sa.conversation_id = c.id "
        f"JOIN users u ON c.user_id = u.id "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY sa.created_at DESC, sa.id DESC "
        f"LIMIT %s"
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
        next_cursor = encode_cursor({"ts": last[10].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def update_alert(
    *,
    tenant_id: str,
    alert_id: str,
    status: str,
    admin_note: str | None,
) -> dict:
    """變更情緒告警狀態 / 備註。

    - 狀態轉移走 _STATUS_TRANSITIONS 白名單；違規回 409 INVALID_TRANSITION。
    - admin_note 為 None 時不更動既有備註（避免誤清空）；空字串 "" 視為清空。
    - 回 200 + 完整 SentimentAlert（response_model 對齊 OpenAPI）。
    """
    if status not in _VALID_STATUSES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"invalid status '{status}'; expected one of {_VALID_STATUSES}",
            422,
        )
    if admin_note is not None and len(admin_note) > 1000:
        raise ApiError(
            "VALIDATION_ERROR",
            "admin_note must be at most 1000 chars",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 先查既有狀態 + tenant 校驗（透過 conversations → users）
    cur = await db_module._conn.execute(
        "SELECT sa.status FROM sentiment_alerts sa "
        "JOIN conversations c ON sa.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE sa.id = %s::uuid AND u.tenant_id = %s::uuid",
        (alert_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Sentiment alert {alert_id} not found", 404)

    current_status = row[0]
    # 同狀態 no-op：允許但不需查 transitions（提升 idempotency）
    if current_status != status and status not in _STATUS_TRANSITIONS[current_status]:
        raise ApiError(
            "INVALID_TRANSITION",
            f"cannot transition from '{current_status}' to '{status}'",
            409,
        )

    # 動態組 SET clause（admin_note=None 時跳過）
    set_clauses = ["status = %s", "updated_at = NOW()"]
    args: list = [status]
    if admin_note is not None:
        set_clauses.append("admin_note = %s")
        args.append(admin_note if admin_note != "" else None)
    args.append(alert_id)

    await db_module._conn.execute(
        f"UPDATE sentiment_alerts SET {', '.join(set_clauses)} WHERE id = %s::uuid",
        args,
    )

    # 回讀完整 row（沿用 list 的 SELECT JOIN）
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM sentiment_alerts sa "
        f"JOIN conversations c ON sa.conversation_id = c.id "
        f"JOIN users u ON c.user_id = u.id "
        f"WHERE sa.id = %s::uuid AND u.tenant_id = %s::uuid",
        (alert_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("DB_ERROR", "Failed to read back updated alert", 500)
    return _row_to_dict(row)
