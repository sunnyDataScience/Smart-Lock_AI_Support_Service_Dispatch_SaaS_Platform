"""Report export service — CSV/PDF 串流匯出。

對應 endpoint：GET /api/v1/reports/export

設計取捨：
  - CSV 行內 stream，記憶體 footprint 不隨 row 數膨脹
  - PDF 路徑回 422 + TODO（缺 reportlab/weasyprint dep；本期不裝）
  - report_type 對應 service 直連，不複製查詢邏輯
  - 篩選 from/to 僅 revenue / technician_ranking 適用，KPI 維持 period 介面

未來擴充：
  - 大筆數異步 job + email 通知（沿用 audit-logs/export 的 200 vs 202 路徑）
  - PDF 支援後改回 200 stream
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from core.errors import ApiError
from services import kpi_service, revenue_service

logger = logging.getLogger("api.report_export_service")


VALID_REPORT_TYPES = {"kpi", "revenue", "technician_ranking"}
VALID_FORMATS = {"csv", "pdf"}


def _csv_line(row: list) -> str:
    """csv.writer auto-quotes fields containing commas / quotes / newlines."""
    buf = io.StringIO()
    csv.writer(buf).writerow(row)
    return buf.getvalue()


def filename(now: datetime, report_type: str, ext: str) -> str:
    return f"{report_type}-{now.strftime('%Y-%m-%d-%H%M')}.{ext}"


# =============================================================================
# CSV row builders — 各 report 自行決定 column 順序與展開規則
# =============================================================================


def _kpi_to_rows(report: dict) -> list[list]:
    """KPI 報表展平：funnel + dispute_rates + technician_efficiency。"""
    rows: list[list] = [["section", "metric", "value"]]
    rows.append(["meta", "period", report.get("period", "")])
    rows.append(["meta", "generated_at", report.get("generated_at", "")])

    for k, v in (report.get("funnel") or {}).items():
        rows.append(["funnel", k, str(v)])

    for k, v in (report.get("dispute_rates") or {}).items():
        rows.append(["dispute_rates", k, "" if v is None else str(v)])

    eff = report.get("technician_efficiency") or {}
    for k, v in eff.items():
        rows.append(["technician_efficiency", k, "" if v is None else str(v)])

    return rows


def _revenue_to_rows(report: dict) -> list[list]:
    """Revenue 展平：先列 KPI，再列月度趨勢，再列品牌占比。"""
    rows: list[list] = [["section", "key", "value"]]
    rows.append(["meta", "granularity", report.get("granularity", "")])

    for k, v in (report.get("kpis") or {}).items():
        rows.append(["kpis", k, "" if v is None else str(v)])

    rows.append([])
    rows.append(["trend", "month", "amount"])
    for point in report.get("trend") or []:
        rows.append(["trend", point.get("month", ""), str(point.get("amount", ""))])

    rows.append([])
    rows.append(["by_brand", "brand", "amount"])
    for point in report.get("by_brand") or []:
        rows.append(
            ["by_brand", point.get("brand", ""), str(point.get("amount", ""))]
        )

    return rows


# =============================================================================
# Public API — async stream interface
# =============================================================================


async def stream_csv(
    *,
    tenant_id: str,
    report_type: str,
    period: str | None = None,
    from_date: str | None = None,  # noqa: ARG001 - 預留 future 使用
    to_date: str | None = None,    # noqa: ARG001
) -> AsyncIterator[str]:
    """產生 CSV 行 generator。"""
    if report_type == "kpi":
        report = await kpi_service.get_kpi_report(
            tenant_id=tenant_id, period=period or "30d"
        )
        rows = _kpi_to_rows(report)
    elif report_type == "revenue":
        report = await revenue_service.get_revenue_summary(tenant_id=tenant_id)
        rows = _revenue_to_rows(report)
    elif report_type == "technician_ranking":
        # 缺乏技師排名 service；先回最小可用 csv（標頭 + 提示），
        # 待後續 admin/reports/technician-ranking endpoint 補上後對接
        rows = [
            ["technician_id", "name", "completed_orders", "avg_rating"],
            ["", "尚未實作技師排行 service，請待後續 endpoint 補上", "", ""],
        ]
    else:
        raise ApiError(
            "VALIDATION_ERROR",
            f"report_type must be one of {sorted(VALID_REPORT_TYPES)}",
            422,
        )

    for row in rows:
        yield _csv_line(row)


def validate_inputs(
    *, report_type: str, fmt: str, period: str | None
) -> None:
    """同步驗證；違反時 raise ApiError 由 router 直接 propagate。"""
    if report_type not in VALID_REPORT_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"report_type must be one of {sorted(VALID_REPORT_TYPES)}",
            422,
        )
    if fmt not in VALID_FORMATS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"format must be one of {sorted(VALID_FORMATS)}",
            422,
        )
    if fmt == "pdf":
        # PDF 渲染未實作（缺 reportlab/weasyprint dep）
        raise ApiError(
            "PDF_NOT_IMPLEMENTED",
            "PDF export not implemented yet (TODO: requires reportlab/weasyprint)",
            422,
        )
    if report_type == "kpi" and period is not None:
        if period not in {"today", "7d", "30d", "90d"}:
            raise ApiError(
                "VALIDATION_ERROR",
                "period must be one of today/7d/30d/90d",
                422,
            )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
