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


# =============================================================================
# Customer detail with history aggregation (GET /customers/{id})
# =============================================================================


async def get_customer(*, tenant_id: str, customer_id: str) -> dict:
    """單筆客戶詳情 + 聚合歷史。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 基本資料
    cur = await db_module._conn.execute(
        f"SELECT {_CUSTOMER_SELECT} FROM users u "
        f"WHERE u.id = %s::uuid AND u.tenant_id = %s::uuid AND u.role = 'line_user'",
        (customer_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Customer not found", 404)
    base = _row_to_customer(row)

    # 工單聚合：依狀態
    cur = await db_module._conn.execute(
        "SELECT wo.status, COUNT(*) "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "WHERE c.user_id = %s::uuid "
        "GROUP BY wo.status",
        (customer_id,),
    )
    status_breakdown: dict[str, int] = {}
    for r in await cur.fetchall():
        status_breakdown[r[0] or "unknown"] = int(r[1])

    # 工單聚合：平均處理時長 + 平均評分
    cur = await db_module._conn.execute(
        "SELECT "
        "  AVG(EXTRACT(EPOCH FROM (wo.completed_at - wo.created_at)) / 60.0) AS avg_minutes, "
        "  AVG(wo.rating) AS avg_rating, "
        "  COUNT(*) FILTER (WHERE wo.rating IS NOT NULL) AS rated_count "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "WHERE c.user_id = %s::uuid AND wo.completed_at IS NOT NULL",
        (customer_id,),
    )
    perf_row = await cur.fetchone()
    avg_minutes = float(perf_row[0]) if perf_row and perf_row[0] is not None else None
    avg_rating = float(perf_row[1]) if perf_row and perf_row[1] is not None else None
    rated_count = int(perf_row[2]) if perf_row and perf_row[2] is not None else 0

    # 投訴 / 爭議次數
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM disputes d WHERE d.filed_by = %s::uuid",
        (customer_id,),
    )
    dispute_count = int((await cur.fetchone())[0])

    # 退款（依 work_order chain）：總額 + 筆數
    cur = await db_module._conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(r.amount), 0) "
        "FROM refund_requests r "
        "JOIN work_orders wo ON r.work_order_id = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "WHERE c.user_id = %s::uuid",
        (customer_id,),
    )
    refund_row = await cur.fetchone()
    refund_count = int(refund_row[0])
    refund_total = float(refund_row[1])

    # 最近工單 (top 10)
    cur = await db_module._conn.execute(
        "SELECT wo.id, wo.status, wo.customer_address, pc.brand, pc.model, "
        "       wo.priority, wo.estimated_price, wo.created_at, wo.completed_at "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "WHERE c.user_id = %s::uuid "
        "ORDER BY wo.created_at DESC LIMIT 10",
        (customer_id,),
    )
    recent_orders = [
        {
            "id": str(r[0]),
            "status": r[1],
            "address": r[2],
            "brand": r[3],
            "model": r[4],
            "priority": r[5],
            "estimated_price": float(r[6]) if r[6] is not None else None,
            "created_at": r[7].isoformat() if r[7] else None,
            "completed_at": r[8].isoformat() if r[8] else None,
        }
        for r in await cur.fetchall()
    ]

    # 最近對話 (top 5)
    cur = await db_module._conn.execute(
        "SELECT id, status, channel, created_at, updated_at "
        "FROM conversations "
        "WHERE user_id = %s::uuid "
        "ORDER BY updated_at DESC LIMIT 5",
        (customer_id,),
    )
    recent_conversations = [
        {
            "id": str(r[0]),
            "status": r[1],
            "channel": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "updated_at": r[4].isoformat() if r[4] else None,
        }
        for r in await cur.fetchall()
    ]

    return {
        **base,
        "history": {
            "work_order_status_breakdown": status_breakdown,
            "avg_completion_minutes": (
                round(avg_minutes, 1) if avg_minutes is not None else None
            ),
            "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
            "rated_count": rated_count,
            "dispute_count": dispute_count,
            "refund_count": refund_count,
            "refund_total": refund_total,
            "recent_orders": recent_orders,
            "recent_conversations": recent_conversations,
        },
    }
