"""Customer Satisfaction Metrics Service — WBS §8 P2「報表 metrics 擴充」。

work_orders.rating (1-5) + feedback 已存在；本 service 聚合：
  - avg_rating / 總評價數 / rated_pct（評價率 = rated / completed）
  - rating distribution (1, 2, 3, 4, 5 各 count)
  - low_rating_pct (1-2 星) / 5_star_pct
  - top_low_rating_recent 5（含 feedback 字段）

對齊 kpi_service 既有「未來擴充」清單之「客戶滿意度 / NPS / 差評率」。

實作不修改既有 kpi_service.py 避免污染 — 走獨立 service + 獨立 endpoint
`/reports/customer-satisfaction`。
"""

from __future__ import annotations

import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.customer_satisfaction_service")


async def get_customer_satisfaction(
    *,
    tenant_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """聚合客戶滿意度 metrics。

    範圍：work_orders 完工 (status IN ('completed', 'confirmed')) 且
    optionally rating 不為 NULL；以 completed_at 為時間軸。

    Returns:
      {
        "tenant_id": str,
        "window": {"start_date": str|None, "end_date": str|None},
        "totals": {
          "total_completed": int,
          "total_rated": int,
          "rated_pct": float,    # rated / completed × 100
        },
        "avg_rating": float|None,
        "rating_distribution": {1: int, 2: int, 3: int, 4: int, 5: int},
        "rates": {
          "low_rating_pct": float,   # (1+2 stars) / total_rated × 100
          "five_star_pct": float,    # 5 stars / total_rated × 100
        },
        "top_low_rating_recent": [
          {id, technician_id, rating, feedback, completed_at}, ...max 5
        ]
      }
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. JOIN 取 work_orders + completed 篩選；可選 date range
    time_clause = ""
    args: list = [tenant_id]
    if start_date and end_date:
        time_clause = " AND wo.completed_at::date BETWEEN %s AND %s"
        args.extend([start_date, end_date])

    base_where = (
        "u.tenant_id = %s::uuid AND wo.completed_at IS NOT NULL"
        + time_clause
    )

    # 2. total_completed / total_rated / avg_rating
    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(*), "
        "  COUNT(*) FILTER (WHERE wo.rating IS NOT NULL), "
        "  AVG(wo.rating) FILTER (WHERE wo.rating IS NOT NULL) "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE {base_where}",
        tuple(args),
    )
    total_row = await cur.fetchone()
    total_completed = int(total_row[0] or 0)
    total_rated = int(total_row[1] or 0)
    avg_rating = float(total_row[2]) if total_row[2] is not None else None
    if avg_rating is not None:
        avg_rating = round(avg_rating, 2)
    rated_pct = (
        round(100.0 * total_rated / total_completed, 2)
        if total_completed > 0 else 0.0
    )

    # 3. rating distribution 1..5
    cur = await db_module._conn.execute(
        "SELECT wo.rating, COUNT(*) "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE {base_where} AND wo.rating IS NOT NULL "
        "GROUP BY wo.rating",
        tuple(args),
    )
    dist_rows = await cur.fetchall()
    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for rating, count in dist_rows:
        if rating in rating_dist:
            rating_dist[int(rating)] = int(count)

    # 4. rates: low_rating_pct (1-2) / five_star_pct
    low_count = rating_dist[1] + rating_dist[2]
    five_count = rating_dist[5]
    low_rating_pct = (
        round(100.0 * low_count / total_rated, 2)
        if total_rated > 0 else 0.0
    )
    five_star_pct = (
        round(100.0 * five_count / total_rated, 2)
        if total_rated > 0 else 0.0
    )

    # 5. top_low_rating_recent 5 (rating <= 2)
    cur = await db_module._conn.execute(
        "SELECT wo.id, wo.technician_id, wo.rating, wo.feedback, wo.completed_at "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE {base_where} AND wo.rating IS NOT NULL AND wo.rating <= 2 "
        "ORDER BY wo.completed_at DESC NULLS LAST "
        "LIMIT 5",
        tuple(args),
    )
    low_rows = await cur.fetchall()
    top_low_rating = [
        {
            "id": str(r[0]),
            "technician_id": str(r[1]) if r[1] else None,
            "rating": int(r[2]),
            "feedback": r[3],
            "completed_at": r[4].isoformat() if r[4] else None,
        }
        for r in low_rows
    ]

    return {
        "tenant_id": tenant_id,
        "window": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "totals": {
            "total_completed": total_completed,
            "total_rated": total_rated,
            "rated_pct": rated_pct,
        },
        "avg_rating": avg_rating,
        "rating_distribution": rating_dist,
        "rates": {
            "low_rating_pct": low_rating_pct,
            "five_star_pct": five_star_pct,
        },
        "top_low_rating_recent": top_low_rating,
    }
