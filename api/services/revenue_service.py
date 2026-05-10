"""Revenue 報表業務邏輯（Phase 1.22 read-only）。

範圍：getRevenueSummary（KPI + 月度 trend + 品牌占比）。
不含：日 / 週 granularity（後端目前僅實作 month）；CSV/Excel 匯出端點。

OpenAPI RevenueSummary：
    granularity, kpis (5 欄位), trend (RevenueTrendPoint[]), by_brand (RevenueByBrandPoint[])

DB ↔ API 對齊：
  - invoices.amount (FLOAT) → 所有 revenue 欄位 decimal string with 2 decimals
  - issued+paid 視為已開立計入營收；draft 視為未收；cancelled 排除
  - 月度趨勢取最近 12 個自然月（含本月），按 issued_at 落入；無 issued_at
    時 fallback created_at（保證 draft 也能落點）
  - 品牌透過 invoices→work_orders→problem_cards.brand JOIN 取得；
    NULL/空字串收斂為「未分類」
  - F-021 串接：可選 start_date / end_date 把 trend / by_brand / KPI（除 month_revenue
    保持「本月」語意外）改用 DB-side filter，避免 client-side 撈滿表

租戶隔離：與 invoice_service 同 4 層 JOIN
    invoices → work_orders → problem_cards → conversations → users.tenant_id
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.revenue_service")


_VALID_GRANULARITY = {"day", "week", "month"}

# DB status 中視為已開立計入營收的值
_REVENUE_STATUSES = ("issued", "paid")
# DB status 中視為未收帳款的值
_OUTSTANDING_STATUSES = ("draft",)


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


_TENANT_JOIN = (
    "FROM invoices i "
    "JOIN work_orders wo ON i.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "JOIN conversations c ON pc.conversation_id = c.id "
    "JOIN users u ON c.user_id = u.id"
)


# 落點欄位：優先 issued_at，draft 走 created_at — 與 trend query 一致
_DATE_FALLBACK = "COALESCE(i.issued_at, i.created_at)"


def _date_range_clause() -> str:
    """Inclusive date range — end_date is included via < end + 1 day."""
    return (
        f"{_DATE_FALLBACK} >= %s::date "
        f"AND {_DATE_FALLBACK} < (%s::date + INTERVAL '1 day')"
    )


def _validate_date_range(
    start_date: date | None,
    end_date: date | None,
) -> None:
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


async def _query_kpis(
    tenant_id: str,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    """5 個 KPI 用一個 SQL with FILTER 子句一次撈出。

    當 start_date/end_date 提供時：所有 KPI 都在該 date range 內計算（含
    month_revenue — 名稱保留但語意變為「期間內」）。
    """
    using_range = start_date is not None and end_date is not None

    if using_range:
        # 期間內：month_revenue 改解讀為「期間內 issued+paid 總額」
        sql = f"""
            SELECT
                COALESCE(SUM(i.amount) FILTER (
                    WHERE i.status IN ('issued','paid')
                ), 0) AS month_revenue,
                COALESCE(AVG(i.amount) FILTER (WHERE i.status IN ('issued','paid')), 0) AS avg_amount,
                COUNT(*) FILTER (WHERE i.status = 'paid') AS paid_count,
                COUNT(*) FILTER (WHERE i.status IN ('issued','paid','cancelled')) AS issued_or_done,
                COALESCE(SUM(i.amount) FILTER (WHERE i.status = 'draft'), 0) AS outstanding_amount,
                COUNT(*) FILTER (WHERE i.status = 'draft') AS outstanding_count
            {_TENANT_JOIN}
            WHERE u.tenant_id = %s::uuid
              AND {_date_range_clause()}
        """
        args: list = [tenant_id, start_date, end_date]
    else:
        # 預設：month_revenue = 本月 issued+paid 總額
        sql = f"""
            SELECT
                COALESCE(SUM(i.amount) FILTER (
                    WHERE i.status IN ('issued','paid')
                      AND date_trunc('month', {_DATE_FALLBACK})
                          = date_trunc('month', NOW())
                ), 0) AS month_revenue,
                COALESCE(AVG(i.amount) FILTER (WHERE i.status IN ('issued','paid')), 0) AS avg_amount,
                COUNT(*) FILTER (WHERE i.status = 'paid') AS paid_count,
                COUNT(*) FILTER (WHERE i.status IN ('issued','paid','cancelled')) AS issued_or_done,
                COALESCE(SUM(i.amount) FILTER (WHERE i.status = 'draft'), 0) AS outstanding_amount,
                COUNT(*) FILTER (WHERE i.status = 'draft') AS outstanding_count
            {_TENANT_JOIN}
            WHERE u.tenant_id = %s::uuid
        """
        args = [tenant_id]

    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()

    month_rev = row[0]
    avg_amount = row[1]
    paid_count = row[2] or 0
    issued_or_done = row[3] or 0
    outstanding_amt = row[4]
    outstanding_cnt = row[5] or 0

    paid_rate = float(paid_count) / float(issued_or_done) if issued_or_done > 0 else None

    return {
        "month_revenue": _coerce_decimal(month_rev),
        "average_invoice_amount": _coerce_decimal(avg_amount),
        "paid_rate": paid_rate,
        "outstanding_amount": _coerce_decimal(outstanding_amt),
        "outstanding_count": int(outstanding_cnt),
    }


async def _query_trend_monthly(
    tenant_id: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    """月度趨勢。預設取最近 12 個月（含本月）；提供 date range 時改取 range 內月份。"""
    if start_date is not None and end_date is not None:
        time_clause = _date_range_clause()
        time_args: list = [start_date, end_date]
    else:
        time_clause = (
            f"{_DATE_FALLBACK} >= date_trunc('month', NOW()) - INTERVAL '11 months'"
        )
        time_args = []

    sql = f"""
        SELECT
            to_char(date_trunc('month', {_DATE_FALLBACK}), 'YYYY-MM') AS period,
            COALESCE(SUM(i.amount), 0) AS revenue,
            COUNT(*) AS order_count
        {_TENANT_JOIN}
        WHERE u.tenant_id = %s::uuid
          AND i.status IN ('issued','paid')
          AND {time_clause}
        GROUP BY date_trunc('month', {_DATE_FALLBACK})
        ORDER BY date_trunc('month', {_DATE_FALLBACK}) ASC
    """
    cur = await db_module._conn.execute(sql, [tenant_id, *time_args])
    rows = await cur.fetchall()
    return [
        {
            "period": r[0],
            "revenue": _coerce_decimal(r[1]),
            "order_count": int(r[2]),
        }
        for r in rows
    ]


async def _query_by_brand(
    tenant_id: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    extra_clause = ""
    extra_args: list = []
    if start_date is not None and end_date is not None:
        extra_clause = f" AND {_date_range_clause()}"
        extra_args = [start_date, end_date]

    sql = f"""
        SELECT
            COALESCE(NULLIF(pc.brand, ''), '未分類') AS brand,
            COALESCE(SUM(i.amount), 0) AS revenue
        {_TENANT_JOIN}
        WHERE u.tenant_id = %s::uuid
          AND i.status IN ('issued','paid'){extra_clause}
        GROUP BY 1
        ORDER BY 2 DESC
    """
    cur = await db_module._conn.execute(sql, [tenant_id, *extra_args])
    rows = await cur.fetchall()

    total = sum(Decimal(str(r[1])) for r in rows) if rows else Decimal("0")
    out: list[dict] = []
    for r in rows:
        rev = Decimal(str(r[1]))
        share = float(rev / total) if total > 0 else 0.0
        out.append({
            "brand": r[0],
            "revenue": _coerce_decimal(r[1]),
            "share": share,
        })
    return out


async def get_revenue_summary(
    *,
    tenant_id: str,
    granularity: str = "month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if granularity not in _VALID_GRANULARITY:
        raise ApiError("VALIDATION_ERROR", f"Invalid granularity: {granularity}", 422)

    _validate_date_range(start_date, end_date)

    # 後端目前僅支援 month；day/week 也回傳 month 結果（前端 segmented control disabled）
    effective = "month"

    kpis = await _query_kpis(tenant_id, start_date, end_date)
    trend = await _query_trend_monthly(tenant_id, start_date, end_date)
    by_brand = await _query_by_brand(tenant_id, start_date, end_date)

    return {
        "granularity": effective,
        "kpis": kpis,
        "trend": trend,
        "by_brand": by_brand,
    }
