"""KPI Report 業務邏輯（read-only 漏斗 + 異常率 + 技師效率）。

GET /api/v1/reports/kpi — 給 /admin/reports/kpi KPI 儀表板。

聚合來源（皆 JOIN users.tenant_id 過濾）：
  - funnel：conversations / problem_cards / work_orders 計數，依 created_at 落在 period
  - dispute_rates：refund_requests / warranty_claims / disputes 數 / work_orders 總數
  - technician_efficiency：AVG(EXTRACT(EPOCH FROM completed_at - started_at)/60) 分鐘

period 採用 dashboard 同 enum（today / 7d / 30d / 90d）。
SLA / NPS / 滿意度 / FTFR / 差評率不在本端點計算（缺乏資料來源 — 無 SLA 規則表
與評價回傳機制）；以 notes 欄位告知前端。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.kpi_service")


_PERIOD_INTERVAL = {
    "today": "0 days",
    "7d": "7 days",
    "30d": "30 days",
    "90d": "90 days",
}


def _period_clause(alias: str) -> str:
    return (
        f"{alias}.created_at >= "
        f"CASE WHEN %s = '0 days' THEN date_trunc('day', NOW()) "
        f"ELSE NOW() - %s::interval END"
    )


def _ratio(numer: int, denom: int) -> str | None:
    if denom <= 0:
        return None
    return f"{(numer / denom):.4f}"


async def _count_conversations(tenant_id: str, interval: str) -> int:
    sql = (
        "SELECT COUNT(*) FROM conversations c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE u.tenant_id = %s::uuid "
        f"AND {_period_clause('c')}"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, interval, interval))
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _count_problem_cards(tenant_id: str, interval: str) -> int:
    sql = (
        "SELECT COUNT(*) FROM problem_cards pc "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE u.tenant_id = %s::uuid "
        f"AND {_period_clause('pc')}"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, interval, interval))
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _count_work_orders(
    tenant_id: str,
    interval: str,
    statuses: tuple[str, ...] | None = None,
) -> int:
    where = ["u.tenant_id = %s::uuid", _period_clause("wo")]
    args: list = [tenant_id, interval, interval]
    if statuses:
        placeholders = ",".join(["%s"] * len(statuses))
        where.append(f"wo.status IN ({placeholders})")
        args.extend(statuses)
    sql = (
        "SELECT COUNT(*) FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        f"WHERE {' AND '.join(where)}"
    )
    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _count_dispute_table(
    tenant_id: str,
    interval: str,
    table: str,
    fk: str = "work_order_id",
) -> int:
    """通用 disputes/refund_requests/warranty_claims 計數
    — 透過 work_orders → problem_cards → conversations → users 路徑。"""
    sql = (
        f"SELECT COUNT(*) FROM {table} t "
        f"JOIN work_orders wo ON t.{fk} = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE u.tenant_id = %s::uuid "
        f"AND {_period_clause('t')}"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, interval, interval))
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _avg_handle_minutes(tenant_id: str, interval: str) -> tuple[float | None, int]:
    """平均處理時長（分鐘）+ 完工樣本數。
    僅取 status IN (completed, confirmed) 且 started_at / completed_at 皆非 NULL。"""
    sql = (
        "SELECT AVG(EXTRACT(EPOCH FROM (wo.completed_at - wo.started_at)) / 60.0), "
        "       COUNT(*) "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE u.tenant_id = %s::uuid "
        "AND wo.status IN ('completed','confirmed') "
        "AND wo.started_at IS NOT NULL "
        "AND wo.completed_at IS NOT NULL "
        f"AND {_period_clause('wo')}"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, interval, interval))
    row = await cur.fetchone()
    avg = float(row[0]) if row[0] is not None else None
    cnt = int(row[1] or 0)
    return avg, cnt


async def get_kpi_report(*, tenant_id: str, period: str) -> dict:
    """GET /reports/kpi。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if period not in _PERIOD_INTERVAL:
        raise ApiError("INVALID_PERIOD", f"period must be one of {list(_PERIOD_INTERVAL)}", 400)
    interval = _PERIOD_INTERVAL[period]

    conversations_n = await _count_conversations(tenant_id, interval)
    problem_cards_n = await _count_problem_cards(tenant_id, interval)
    work_orders_n = await _count_work_orders(tenant_id, interval)
    dispatched_n = await _count_work_orders(
        tenant_id,
        interval,
        statuses=("assigned", "accepted", "in_progress", "completed", "confirmed"),
    )
    completed_n = await _count_work_orders(
        tenant_id,
        interval,
        statuses=("completed", "confirmed"),
    )

    refund_n = await _count_dispute_table(tenant_id, interval, "refund_requests")
    warranty_n = await _count_dispute_table(tenant_id, interval, "warranty_claims")
    dispute_n = await _count_dispute_table(tenant_id, interval, "disputes")

    avg_min, completed_cnt = await _avg_handle_minutes(tenant_id, interval)

    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "funnel": {
            "conversations": conversations_n,
            "problem_cards": problem_cards_n,
            "work_orders": work_orders_n,
            "dispatched": dispatched_n,
            "completed": completed_n,
        },
        "dispute_rates": {
            "refund_rate": _ratio(refund_n, work_orders_n),
            "warranty_claim_rate": _ratio(warranty_n, work_orders_n),
            "dispute_rate": _ratio(dispute_n, work_orders_n),
        },
        "technician_efficiency": {
            "avg_handle_minutes": round(avg_min, 1) if avg_min is not None else None,
            "completed_count": completed_cnt,
        },
        "notes": [
            "SLA 達成率：尚無 SLA 規則與計算引擎",
            "客戶滿意度（星等 / 差評率）：尚無評價回傳機制",
            "NPS 淨推薦值：尚無 NPS 調查管道",
            "FTFR 一次修好率：尚無 rework 標記欄位",
        ],
    }
