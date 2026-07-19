"""KPI Report 業務邏輯（read-only 漏斗 + 異常率 + 技師效率）。

GET /api/v1/reports/kpi — 給 /admin/reports/kpi KPI 儀表板。

聚合來源（皆 JOIN users.tenant_id 過濾）：
  - funnel：以期間內建立的 conversations 為 cohort，各階段計「推進到該階段的
    對話數」（UAT P3：cohort 化保證遞減鏈，轉換率恆 ≤ 100%）
  - dispute_rates：refund_requests / warranty_claims / disputes 數 / work_orders 總數
  - technician_efficiency：AVG(completed_at - 真實開工錨) 分鐘——started_at 早於
    completed_at 才視為真到場，否則 fallback created_at（UAT R3：完工自動補的
    started_at==completed_at 會把平均灌成 0）

period 採用 dashboard 同 enum（today / 7d / 30d / 90d）。
若呼叫端提供 start_date / end_date，date range 覆蓋 period（F-021 Dashboard
DateRangePicker 串接，DB-side filter 取代 client-side filter）。
SLA / NPS / 滿意度 / FTFR / 差評率不在本端點計算（缺乏資料來源 — 無 SLA 規則表
與評價回傳機制）；以 notes 欄位告知前端。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

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


def _date_range_clause(alias: str) -> str:
    """Inclusive date range — ``end_date`` is included via ``< end + 1 day``。"""
    return (
        f"{alias}.created_at >= %s::date "
        f"AND {alias}.created_at < (%s::date + INTERVAL '1 day')"
    )


def _ratio(numer: int, denom: int) -> str | None:
    if denom <= 0:
        return None
    return f"{(numer / denom):.4f}"


def _build_time_filter(
    alias: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[str, list]:
    """Pick date-range when caller supplied dates, else fall back to period."""
    if start_date is not None and end_date is not None:
        return _date_range_clause(alias), [start_date, end_date]
    return _period_clause(alias), [interval, interval]


async def _funnel_counts(
    tenant_id: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    """轉換漏斗（UAT P3 修正）：以「期間內建立的對話」為單一 cohort，各階段計
    「該 cohort 中推進到此階段的對話數」。

    舊算法各階段依自身 created_at 各自計數——期間內開的工單可對應期間外的
    對話，工單數＞對話數 → 前端以首階段為分母算出 300% 假轉換率。cohort 化
    後各階段為前一階段的子集（嚴格遞減鏈），百分比恆 ≤ 100%。
    """
    clause, time_args = _build_time_filter("c", interval, start_date, end_date)
    _wo_exists = (
        "SELECT 1 FROM problem_cards pc "
        "JOIN work_orders wo ON wo.problem_card_id = pc.id "
        "WHERE pc.conversation_id = c.id"
    )
    sql = (
        "SELECT COUNT(*), "
        "  COUNT(*) FILTER (WHERE EXISTS ("
        "    SELECT 1 FROM problem_cards pc WHERE pc.conversation_id = c.id)), "
        f"  COUNT(*) FILTER (WHERE EXISTS ({_wo_exists})), "
        f"  COUNT(*) FILTER (WHERE EXISTS ({_wo_exists} "
        "    AND wo.status IN ('assigned','accepted','in_progress','completed','confirmed'))), "
        f"  COUNT(*) FILTER (WHERE EXISTS ({_wo_exists} "
        "    AND wo.status IN ('completed','confirmed'))) "
        "FROM conversations c "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE u.tenant_id = %s::uuid "
        f"AND {clause}"
    )
    cur = await db_module._conn.execute(sql, [tenant_id, *time_args])
    row = await cur.fetchone()
    return {
        "conversations": int(row[0] or 0),
        "problem_cards": int(row[1] or 0),
        "work_orders": int(row[2] or 0),
        "dispatched": int(row[3] or 0),
        "completed": int(row[4] or 0),
    }


async def _count_work_orders(
    tenant_id: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
    statuses: tuple[str, ...] | None = None,
) -> int:
    clause, time_args = _build_time_filter("wo", interval, start_date, end_date)
    where = ["u.tenant_id = %s::uuid", clause]
    args: list = [tenant_id, *time_args]
    if statuses:
        placeholders = ",".join(["%s"] * len(statuses))
        where.append(f"wo.status IN ({placeholders})")
        args.extend(statuses)
    sql = (
        "SELECT COUNT(*) FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE {' AND '.join(where)}"
    )
    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _ftfr(
    tenant_id: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[str | None, int]:
    """一次修好率 FTFR（first-time fix rate）。

    - 分母 originals：期間內完工（status completed/confirmed）、非返工（is_rework=FALSE）的「原始工單」
    - 分子 first_time：上述工單中，未被任何工單以 rework_of_id 指回（即沒被重做過）
    回 (rate_str | None, originals 樣本數)；分母為 0 時 rate=None。
    依據 work_orders.is_rework / rework_of_id（過往以「尚無 rework 欄」為由列為待接入，欄位現已存在）。
    """
    clause, time_args = _build_time_filter("wo", interval, start_date, end_date)
    sql = (
        "SELECT "
        "  COUNT(*) AS originals, "
        "  COUNT(*) FILTER (WHERE NOT EXISTS ("
        "    SELECT 1 FROM work_orders r WHERE r.rework_of_id = wo.id"
        "  )) AS first_time "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid "
        f"AND {clause} "
        "AND wo.status IN ('completed', 'confirmed') "
        "AND COALESCE(wo.is_rework, FALSE) = FALSE"
    )
    cur = await db_module._conn.execute(sql, [tenant_id, *time_args])
    row = await cur.fetchone()
    originals = int(row[0] or 0)
    first_time = int(row[1] or 0)
    return _ratio(first_time, originals), originals


async def _count_dispute_table(
    tenant_id: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
    table: str,
    fk: str = "work_order_id",
) -> int:
    """通用 disputes/refund_requests/warranty_claims 計數
    — 透過 work_orders → problem_cards → conversations → users 路徑。"""
    clause, time_args = _build_time_filter("t", interval, start_date, end_date)
    sql = (
        f"SELECT COUNT(*) FROM {table} t "
        f"JOIN work_orders wo ON t.{fk} = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid "
        f"AND {clause}"
    )
    cur = await db_module._conn.execute(sql, [tenant_id, *time_args])
    row = await cur.fetchone()
    return int(row[0] or 0)


async def _avg_handle_minutes(
    tenant_id: str,
    interval: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[float | None, int]:
    """平均處理時長（分鐘）+ 完工樣本數。
    僅取 status IN (completed, confirmed) 且 completed_at 非 NULL。

    UAT R3 算式 bug 修正：complete_order 在完工同一句 SQL 補
    `started_at = COALESCE(started_at, NOW())` —— 技師沒按過「到場」的單
    started_at == completed_at → 時長恆 0，AVG 被灌成 0.0（實測兩筆完工
    62/4 分應 ~33，回 0.0）。起點錨改「真實開工時間」：started_at 早於
    completed_at 才採用（真到場紀錄），否則 fallback wo.created_at
    （與客戶詳情頁 avg_minutes 同口徑）。"""
    clause, time_args = _build_time_filter("wo", interval, start_date, end_date)
    sql = (
        "SELECT AVG(EXTRACT(EPOCH FROM (wo.completed_at - "
        "       CASE WHEN wo.started_at IS NOT NULL AND wo.started_at < wo.completed_at "
        "            THEN wo.started_at ELSE wo.created_at END)) / 60.0), "
        "       COUNT(*) "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid "
        "AND wo.status IN ('completed','confirmed') "
        "AND wo.completed_at IS NOT NULL "
        f"AND {clause}"
    )
    cur = await db_module._conn.execute(sql, [tenant_id, *time_args])
    row = await cur.fetchone()
    avg = float(row[0]) if row[0] is not None else None
    cnt = int(row[1] or 0)
    return avg, cnt


def _validate_date_range(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date | None, date | None]:
    """Either both dates or neither; start <= end."""
    if (start_date is None) ^ (end_date is None):
        raise ApiError(
            "VALIDATION_ERROR",
            "start_date and end_date must be provided together",
            422,
        )
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ApiError(
            "VALIDATION_ERROR",
            "start_date must be <= end_date",
            422,
        )
    return start_date, end_date


async def get_kpi_report(
    *,
    tenant_id: str,
    period: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """GET /reports/kpi。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if period not in _PERIOD_INTERVAL:
        raise ApiError("INVALID_PERIOD", f"period must be one of {list(_PERIOD_INTERVAL)}", 400)
    interval = _PERIOD_INTERVAL[period]

    start_date, end_date = _validate_date_range(start_date, end_date)

    # UAT P3：漏斗改 cohort 計數（同一批期間內對話逐階段遞減，轉換率恆 ≤ 100%）
    funnel = await _funnel_counts(tenant_id, interval, start_date, end_date)
    # 異常率分母維持「期間內建立的工單」絕對數（與漏斗 cohort 口徑分離）
    work_orders_n = await _count_work_orders(tenant_id, interval, start_date, end_date)

    refund_n = await _count_dispute_table(
        tenant_id, interval, start_date, end_date, "refund_requests"
    )
    warranty_n = await _count_dispute_table(
        tenant_id, interval, start_date, end_date, "warranty_claims"
    )
    dispute_n = await _count_dispute_table(
        tenant_id, interval, start_date, end_date, "disputes"
    )

    avg_min, completed_cnt = await _avg_handle_minutes(
        tenant_id, interval, start_date, end_date
    )

    ftfr_rate, ftfr_sample = await _ftfr(tenant_id, interval, start_date, end_date)

    # 使用 date range 時，period 仍回傳呼叫端送的值（schema 限制：DashboardPeriod
    # enum 沒有 "custom"），實際時間區間以 start_date / end_date 為準。
    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "funnel": funnel,
        "dispute_rates": {
            "refund_rate": _ratio(refund_n, work_orders_n),
            "warranty_claim_rate": _ratio(warranty_n, work_orders_n),
            "dispute_rate": _ratio(dispute_n, work_orders_n),
        },
        "technician_efficiency": {
            "avg_handle_minutes": round(avg_min, 1) if avg_min is not None else None,
            "completed_count": completed_cnt,
            "ftfr": ftfr_rate,
            "ftfr_sample": ftfr_sample,
        },
        "notes": [
            "SLA 達成率：尚無 SLA 規則與計算引擎",
            "客戶滿意度（星等 / 差評率）：尚無評價回傳機制",
            "NPS 淨推薦值：尚無 NPS 調查管道",
        ],
    }
