"""Operational KPI Metrics Service — WBS §8 P2「報表 metrics 擴充」收尾。

對齊 `reports_kpi.py` docstring 既標的「未來擴充」項目：
  - FTFR (First Time Fix Rate) — `rework_of_id` 業務邏輯
  - SLA 達成率（基於 sla_monitor 既有閾值）

實作：
  - FTFR: 完工 wo 中「未被當作 rework 來源」的比率
  - dispatch_on_time_pct: created → assigned ≤ SLA_DISPATCH_DELAY_MINUTES
  - arrival_on_time_pct: scheduled_at ≤ started_at ≤ scheduled_at +
                          SLA_ARRIVAL_OVERDUE_MINUTES（業務 PM Q5=B soft SLA）

不修 sla_monitor.py — SLA breach 為 in-memory alert，本 service 從
work_orders 欄位推算「達成率」（事後聚合）。
"""

from __future__ import annotations

import logging
import os
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.operational_kpi_service")

# 對齊 sla_monitor.py 的同名 env 預設
DISPATCH_DELAY_MINUTES = int(os.environ.get("SLA_DISPATCH_DELAY_MINUTES", "30"))
ARRIVAL_OVERDUE_MINUTES = int(os.environ.get("SLA_ARRIVAL_OVERDUE_MINUTES", "120"))


async def get_operational_kpi(
    *,
    tenant_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """聚合 operational KPI：FTFR + SLA 達成率。

    Returns:
      {
        "tenant_id": str,
        "window": {"start_date", "end_date"},
        "ftfr": {
          "total_completed": int,
          "rework_source_count": int,   # 被當作 rework 來源的 wo 數
          "ftfr_pct": float,            # (1 - rework/completed) × 100
        },
        "sla": {
          "dispatch_delay_threshold_min": int,
          "arrival_overdue_threshold_min": int,
          "dispatch_on_time_pct": float,
          "arrival_on_time_pct": float,
        },
      }
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # build time filter
    args_base: list = [tenant_id]
    time_clause = ""
    if start_date and end_date:
        time_clause = " AND wo.completed_at::date BETWEEN %s AND %s"
        args_base.extend([start_date, end_date])
    base_where = (
        "u.tenant_id = %s::uuid AND wo.completed_at IS NOT NULL"
        + time_clause
    )
    join_clause = (
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
    )

    # 1. FTFR：總完工 wo / 被當作 rework_of_id 的 wo 數
    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(DISTINCT wo.id), "
        "  COUNT(DISTINCT wo2.rework_of_id) "
        f"FROM work_orders wo {join_clause}"
        "LEFT JOIN work_orders wo2 ON wo2.rework_of_id = wo.id "
        f"WHERE {base_where}",
        tuple(args_base),
    )
    ftfr_row = await cur.fetchone()
    total_completed = int(ftfr_row[0] or 0)
    rework_source_count = int(ftfr_row[1] or 0)
    ftfr_pct = (
        round(100.0 * (total_completed - rework_source_count) / total_completed, 2)
        if total_completed > 0 else 0.0
    )

    # 2. dispatch_on_time_pct：accepted_at - created_at ≤ threshold（MVP 簡化）
    # 注：DISPATCH_DELAY_MINUTES 為 module-level int 常數安全 f-string interpolate
    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE wo.accepted_at IS NOT NULL), "
        "  COUNT(*) FILTER (WHERE wo.accepted_at IS NOT NULL "
        f"                  AND wo.accepted_at <= wo.created_at + INTERVAL '{DISPATCH_DELAY_MINUTES} minutes') "
        f"FROM work_orders wo {join_clause}"
        f"WHERE {base_where}",
        tuple(args_base),
    )
    disp_row = await cur.fetchone()
    dispatch_total = int(disp_row[0] or 0)
    dispatch_on_time = int(disp_row[1] or 0)
    dispatch_on_time_pct = (
        round(100.0 * dispatch_on_time / dispatch_total, 2)
        if dispatch_total > 0 else 0.0
    )

    # 3. arrival_on_time_pct：started_at ≤ scheduled_at + threshold
    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE wo.started_at IS NOT NULL AND wo.scheduled_at IS NOT NULL), "
        "  COUNT(*) FILTER (WHERE wo.started_at IS NOT NULL AND wo.scheduled_at IS NOT NULL "
        f"                  AND wo.started_at <= wo.scheduled_at + INTERVAL '{ARRIVAL_OVERDUE_MINUTES} minutes') "
        f"FROM work_orders wo {join_clause}"
        f"WHERE {base_where}",
        tuple(args_base),
    )
    arr_row = await cur.fetchone()
    arrival_total = int(arr_row[0] or 0)
    arrival_on_time = int(arr_row[1] or 0)
    arrival_on_time_pct = (
        round(100.0 * arrival_on_time / arrival_total, 2)
        if arrival_total > 0 else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "window": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "ftfr": {
            "total_completed": total_completed,
            "rework_source_count": rework_source_count,
            "ftfr_pct": ftfr_pct,
        },
        "sla": {
            "dispatch_delay_threshold_min": DISPATCH_DELAY_MINUTES,
            "arrival_overdue_threshold_min": ARRIVAL_OVERDUE_MINUTES,
            "dispatch_on_time_pct": dispatch_on_time_pct,
            "arrival_on_time_pct": arrival_on_time_pct,
        },
    }
