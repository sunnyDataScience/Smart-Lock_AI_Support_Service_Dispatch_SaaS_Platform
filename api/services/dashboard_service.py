"""Dashboard 統計聚合服務。

GET /api/v1/dashboard/stats — 給 /dashboard 首頁 KPI 卡與排行榜。

聚合來源：
  - conversations + users (JOIN tenant)：總數、狀態分布、AI 解決率、平均解決時間、層級分布
  - problem_cards (JOIN conversations → users)：hot_topics（category）、top_brands（brand）
  - messages.metadata.token_usage：累計 token 用量與估算成本

租戶隔離：所有查詢透過 users.tenant_id JOIN 過濾（沿用 Phase 1.4 conversations pattern）。
Period filter：today 用 date_trunc('day', NOW())；7d/30d/90d 用 NOW() - INTERVAL。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services.conversation_service import (
    _DB_RESOLUTION_TO_API,
    _DB_STATUS_TO_API,
)
from services import technician_service, work_order_service

logger = logging.getLogger("api.dashboard_service")


_PERIOD_INTERVAL = {
    "today": "0 days",
    "7d": "7 days",
    "30d": "30 days",
    "90d": "90 days",
}

# Gemini 2.5 Pro 平均單價（$/token，輸入+輸出 blended）— MVP 階段硬編
_TOKEN_COST_USD = 0.00000125


def _period_clause(alias: str) -> str:
    """產生 period filter SQL 片段。

    使用 CASE 判斷：'0 days' (today) → date_trunc，其他 → NOW() - interval。
    placeholder 出現兩次（CASE WHEN + ELSE），呼叫端要綁兩次相同的 interval。
    """
    return (
        f"{alias}.created_at >= "
        f"CASE WHEN %s = '0 days' THEN date_trunc('day', NOW()) "
        f"ELSE NOW() - %s::interval END"
    )


async def get_stats(*, tenant_id: str, period: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    interval = _PERIOD_INTERVAL[period]

    # 1) Conversations 計數 + Resolution 聚合（一次 GROUP BY）
    conv_sql = (
        f"SELECT c.status, c.resolution_layer, "
        f"       EXTRACT(EPOCH FROM (c.resolved_at - c.started_at)) AS dur_sec "
        f"FROM conversations c JOIN users u ON c.user_id = u.id "
        f"WHERE u.tenant_id = %s::uuid AND {_period_clause('c')}"
    )
    cur = await db_module._conn.execute(conv_sql, (tenant_id, interval, interval))
    conv_rows = await cur.fetchall()

    counts = {"total": 0, "active": 0, "resolved": 0, "escalated": 0}
    by_layer = {"case_library": 0, "rag": 0, "human": 0}
    durations: list[float] = []
    layer_total = 0
    layer_ai = 0  # L1 + L2

    for db_status, db_layer, dur_sec in conv_rows:
        counts["total"] += 1
        api_status = _DB_STATUS_TO_API.get(db_status or "", "active")
        if api_status == "active":
            counts["active"] += 1
        elif api_status == "closed":
            counts["resolved"] += 1
        elif api_status == "waiting_human":
            counts["escalated"] += 1

        if db_layer:
            layer_total += 1
            api_layer = _DB_RESOLUTION_TO_API.get(db_layer)
            if api_layer in by_layer:
                by_layer[api_layer] += 1
            if db_layer in ("L1", "L2"):
                layer_ai += 1

        if dur_sec is not None:
            durations.append(float(dur_sec))

    ai_rate = (layer_ai / layer_total) if layer_total > 0 else None
    avg_dur = int(sum(durations) / len(durations)) if durations else None

    # 2) Hot topics — problem_cards.category
    hot_sql = (
        f"SELECT pc.category, COUNT(*) AS n "
        f"FROM problem_cards pc "
        f"LEFT JOIN conversations c ON pc.conversation_id = c.id "
        f"LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid AND {_period_clause('pc')} "
        f"  AND pc.category IS NOT NULL "
        f"GROUP BY pc.category ORDER BY n DESC LIMIT 5"
    )
    cur = await db_module._conn.execute(hot_sql, (tenant_id, interval, interval))
    hot_topics = [
        {"topic": row[0], "count": int(row[1])} for row in await cur.fetchall()
    ]

    # 3) Top brands — problem_cards.brand
    brand_sql = (
        f"SELECT pc.brand, COUNT(*) AS n "
        f"FROM problem_cards pc "
        f"LEFT JOIN conversations c ON pc.conversation_id = c.id "
        f"LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid AND {_period_clause('pc')} "
        f"  AND pc.brand IS NOT NULL "
        f"GROUP BY pc.brand ORDER BY n DESC LIMIT 5"
    )
    cur = await db_module._conn.execute(brand_sql, (tenant_id, interval, interval))
    top_brands = [
        {"brand": row[0], "count": int(row[1])} for row in await cur.fetchall()
    ]

    # 4) Token usage — messages.metadata.token_usage
    token_sql = (
        f"SELECT "
        f"  COALESCE(SUM((m.metadata->'token_usage'->>'total')::int), 0) AS total, "
        f"  COALESCE(SUM((m.metadata->'token_usage'->>'prompt')::int), 0) AS prompt, "
        f"  COALESCE(SUM((m.metadata->'token_usage'->>'completion')::int), 0) AS completion "
        f"FROM messages m "
        f"JOIN conversations c ON m.conversation_id = c.id "
        f"LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE u.tenant_id = %s::uuid AND {_period_clause('m')}"
    )
    cur = await db_module._conn.execute(token_sql, (tenant_id, interval, interval))
    trow = await cur.fetchone()
    total_tokens = int(trow[0] or 0) if trow else 0
    prompt_tokens = int(trow[1] or 0) if trow else 0
    completion_tokens = int(trow[2] or 0) if trow else 0
    estimated_cost = round(total_tokens * _TOKEN_COST_USD, 6)

    # 5) Work-order today KPIs（period 無關，固定取今日）
    work_orders_stats = await work_order_service.get_today_stats(tenant_id=tenant_id)

    # 6) Technicians 概況（active / online / dispatchable）
    technicians_stats = await technician_service.get_dashboard_stats(tenant_id=tenant_id)

    return {
        "period": period,
        "conversations": counts,
        "resolution": {
            "ai_resolution_rate": ai_rate,
            "avg_resolution_time_seconds": avg_dur,
            "by_layer": by_layer,
        },
        "hot_topics": hot_topics,
        "token_usage": {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
        },
        "top_brands": top_brands,
        "work_orders": work_orders_stats,
        "technicians": technicians_stats,
    }
