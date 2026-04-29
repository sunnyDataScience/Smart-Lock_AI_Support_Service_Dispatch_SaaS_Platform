"""Customers 業務邏輯（read-only 客戶主檔）。

讀 users 表 WHERE role='line_user'，外加 LEFT JOIN 聚合：
  - total_conversations：COUNT(conversations) WHERE user_id = u.id
  - total_orders：COUNT(work_orders) WHERE problem_card → conversation.user_id = u.id
  - last_service_at：MAX(work_orders.completed_at) 同 path

display_name fallback 順序：
  users.display_name → phone → "User {first 6 of id}"

租戶隔離：users.tenant_id 直接過濾。Cursor: (created_at, id) 倒序。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.customer_service")


# 子查詢用 LEFT JOIN LATERAL 或 SELECT subquery 都可；此處選 SELECT subquery
# 可讀性較佳，且 PostgreSQL planner 可優化成 hash aggregate。
_CUSTOMER_SELECT = """
    u.id,
    u.display_name,
    u.line_user_id,
    u.phone,
    u.address,
    u.last_active_at,
    u.created_at,
    COALESCE((
        SELECT COUNT(*) FROM conversations c
        WHERE c.user_id = u.id
    ), 0) AS total_conversations,
    COALESCE((
        SELECT COUNT(*) FROM work_orders wo
        JOIN problem_cards pc ON wo.problem_card_id = pc.id
        JOIN conversations c2 ON pc.conversation_id = c2.id
        WHERE c2.user_id = u.id
    ), 0) AS total_orders,
    (
        SELECT MAX(wo.completed_at) FROM work_orders wo
        JOIN problem_cards pc ON wo.problem_card_id = pc.id
        JOIN conversations c3 ON pc.conversation_id = c3.id
        WHERE c3.user_id = u.id
    ) AS last_service_at
"""


def _derive_display_name(display_name: str | None, phone: str | None, uid: str) -> str:
    if display_name:
        return display_name
    if phone:
        return phone
    return f"User {uid[:6]}"


def _row_to_customer(row: tuple) -> dict:
    """row 順序對齊 _CUSTOMER_SELECT。"""
    uid = str(row[0])
    out: dict = {
        "id": uid,
        "display_name": _derive_display_name(row[1], row[3], uid),
        "line_user_id": row[2],
        "phone": row[3],
        "address": row[4],
        "last_active_at": row[5].isoformat() if row[5] else None,
        "created_at": row[6].isoformat() if row[6] else None,
        "total_conversations": int(row[7] or 0),
        "total_orders": int(row[8] or 0),
        "last_service_at": row[9].isoformat() if row[9] else None,
    }
    return out


async def list_customers(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /customers — 管理員視角，cursor 分頁。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid", "u.role = 'line_user'"]
    args: list = [tenant_id]

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(u.created_at, u.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_CUSTOMER_SELECT} FROM users u "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY u.created_at DESC, u.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_customer(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
