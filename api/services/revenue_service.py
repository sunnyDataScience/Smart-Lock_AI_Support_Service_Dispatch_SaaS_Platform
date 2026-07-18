"""Revenue 報表業務邏輯（Phase 1.22 read-only）。

範圍：getRevenueSummary（KPI + trend + 品牌占比）。
trend 支援 day / week / month / quarter 四種粒度（date_trunc 分桶，_GRANULARITY_SPEC）；
kpis / by_brand / by_category 為區間彙總、與粒度無關。不含：CSV/Excel 匯出端點。

OpenAPI RevenueSummary：
    granularity, kpis (5 欄位), trend (RevenueTrendPoint[]), by_brand (RevenueByBrandPoint[]),
    by_category (RevenueByCategoryPoint[] — additive；問題類別營收佔比，同 by_brand JOIN)

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


_VALID_GRANULARITY = {"day", "week", "month", "quarter"}

# granularity → (date_trunc 單位, to_char 期別格式, 無 date range 時的預設回溯視窗)。
# date_trunc 第一參數與 to_char 格式皆以 %s 帶入（granularity 已先過 _VALID_GRANULARITY 白名單，無注入風險）。
_GRANULARITY_SPEC: dict[str, tuple[str, str, str]] = {
    "day": ("day", "YYYY-MM-DD", "29 days"),        # 近 30 日
    "week": ("week", "YYYY-MM-DD", "83 days"),       # 近 12 週（週起日）
    "month": ("month", "YYYY-MM", "11 months"),      # 近 12 月
    "quarter": ("quarter", 'YYYY"-Q"Q', "21 months"),  # 近 8 季
}

# DB status 中視為已開立計入營收的值
_REVENUE_STATUSES = ("issued", "paid")
# DB status 中視為未收帳款的值。
# UAT-0718 W1-3 口徑修正：未收帳款＝「尚未收到的錢」＝ draft（未請款）+
# issued（已開立但未付款）。原只算 draft → 已開立未付的發票憑空消失，
# 出現「本月營收 >0、付款成功率 0%、未收帳款 NT$0」同頁矛盾。
# paid 已收、cancelled 作廢，皆不計入。
_OUTSTANDING_STATUSES = ("draft", "issued")


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


_TENANT_JOIN = (
    "FROM invoices i "
    "JOIN work_orders wo ON i.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "LEFT JOIN conversations c ON pc.conversation_id = c.id "
    "LEFT JOIN users u ON c.user_id = u.id"
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
                COALESCE(SUM(i.amount) FILTER (WHERE i.status IN ('draft','issued')), 0) AS outstanding_amount,
                COUNT(*) FILTER (WHERE i.status IN ('draft','issued')) AS outstanding_count
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
                COALESCE(SUM(i.amount) FILTER (WHERE i.status IN ('draft','issued')), 0) AS outstanding_amount,
                COUNT(*) FILTER (WHERE i.status IN ('draft','issued')) AS outstanding_count
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

    # 無已開立發票時 paid_rate=0.0（非 None）：RevenueKpis.paid_rate 為 required number，
    # 回 None 會讓 RevenueSummary 序列化失敗（v2 與 legacy /revenue 同 code 皆受影響）。
    paid_rate = float(paid_count) / float(issued_or_done) if issued_or_done > 0 else 0.0

    return {
        "month_revenue": _coerce_decimal(month_rev),
        "average_invoice_amount": _coerce_decimal(avg_amount),
        "paid_rate": paid_rate,
        "outstanding_amount": _coerce_decimal(outstanding_amt),
        "outstanding_count": int(outstanding_cnt),
    }


async def _query_trend(
    tenant_id: str,
    granularity: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    """趨勢分桶。依 granularity 以 date_trunc（日/週/月/季）分組；提供 date range 時取 range 內、
    否則取該粒度的預設回溯視窗（近 30 日 / 12 週 / 12 月 / 8 季）。

    date_trunc 單位與 to_char 格式以參數帶入（granularity 已過白名單）。
    """
    trunc_unit, period_fmt, default_interval = _GRANULARITY_SPEC[granularity]

    # trunc_unit / period_fmt / default_interval 皆源自 _GRANULARITY_SPEC 白名單（無用戶輸入），
    # 直接內插為字面值——若改用 %s 參數化，SELECT 與 GROUP BY 的 date_trunc 會綁到不同 $n、
    # Postgres 視為不同運算式而報 GROUPING 錯。tenant_id 與日期值仍走參數化。
    bucket = f"date_trunc('{trunc_unit}', {_DATE_FALLBACK})"

    if start_date is not None and end_date is not None:
        time_clause = _date_range_clause()
        time_args: list = [start_date, end_date]
    else:
        time_clause = (
            f"{_DATE_FALLBACK} >= date_trunc('{trunc_unit}', NOW()) "
            f"- INTERVAL '{default_interval}'"
        )
        time_args = []

    sql = f"""
        SELECT
            to_char({bucket}, '{period_fmt}') AS period,
            COALESCE(SUM(i.amount), 0) AS revenue,
            COUNT(*) AS order_count
        {_TENANT_JOIN}
        WHERE u.tenant_id = %s::uuid
          AND i.status IN ('issued','paid')
          AND {time_clause}
        GROUP BY {bucket}
        ORDER BY {bucket} ASC
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


async def _query_by_category(
    tenant_id: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    """問題類別營收佔比（與 by_brand 同一條 _TENANT_JOIN，僅 GROUP BY 維度換成 pc.category）。

    pc.category 為自由字串（卡片 / 指紋辨識 / 密碼 / WiFi 連線 / 電池 / 聲音異常 /
    故障 / 安裝…），NULL/空字串收斂為「未分類」。

    注意：這是「問題類別」而非 work_orders.service_category（install/repair/warranty
    enum，目前 seed 未填、全 NULL）；前端圖表標題對應為「問題類別營收佔比」，不可標
    「服務類型」以免語意不符。
    """
    extra_clause = ""
    extra_args: list = []
    if start_date is not None and end_date is not None:
        extra_clause = f" AND {_date_range_clause()}"
        extra_args = [start_date, end_date]

    sql = f"""
        SELECT
            COALESCE(NULLIF(pc.category, ''), '未分類') AS category,
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
            "category": r[0],
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

    # trend 依 granularity 真實分桶（日/週/月/季）；kpis / by_brand / by_category 為
    # 區間彙總，與粒度無關（分桶只影響 trend 的柱數）。
    kpis = await _query_kpis(tenant_id, start_date, end_date)
    trend = await _query_trend(tenant_id, granularity, start_date, end_date)
    by_brand = await _query_by_brand(tenant_id, start_date, end_date)
    by_category = await _query_by_category(tenant_id, start_date, end_date)

    return {
        "granularity": granularity,
        "kpis": kpis,
        "trend": trend,
        "by_brand": by_brand,
        "by_category": by_category,
    }
