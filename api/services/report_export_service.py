"""Report export service — CSV/PDF 串流匯出。

對應 endpoint：GET /api/v1/reports/export

設計取捨：
  - CSV 行內 stream，記憶體 footprint 不隨 row 數膨脹
  - PDF 整檔生成（reportlab SimpleDocTemplate 需一次性 build），bytes 一次 yield
  - report_type 對應 service 直連，不複製查詢邏輯
  - row builder 共用：CSV 與 PDF 共享同一份 rows，只是 render 方式不同
  - 篩選 from/to 僅 revenue / technician_ranking 適用，KPI 維持 period 介面
  - accounting：reuse settlement_service.list_settlements（無 cursor，匯出取首批）

繁中字體策略：
  - 採 reportlab 內建 CID 字型 STSong-Light（Adobe-GB1，無需外部 TTF）
  - 與 voucher_service.py 同 pattern；延遲 register 避免 import overhead

未來擴充：
  - 大筆數異步 job + email 通知（沿用 audit-logs/export 的 200 vs 202 路徑）
  - accounting 加 cursor 分頁串流（目前單批匯出取 list_settlements 預設 limit）
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from core.errors import ApiError
from services import (
    kpi_service,
    revenue_service,
    settlement_service,
)

logger = logging.getLogger("api.report_export_service")


VALID_REPORT_TYPES = {"kpi", "revenue", "technician_ranking", "accounting"}
VALID_FORMATS = {"csv", "pdf"}

# accounting 單檔匯出上限（OpenAPI 預設 limit=20，但匯出場景需要更大批次）
_ACCOUNTING_EXPORT_LIMIT = 500


# =============================================================================
# 共用工具
# =============================================================================


def _csv_line(row: list) -> str:
    """csv.writer auto-quotes fields containing commas / quotes / newlines."""
    buf = io.StringIO()
    csv.writer(buf).writerow(row)
    return buf.getvalue()


def filename(now: datetime, report_type: str, ext: str) -> str:
    return f"{report_type}-{now.strftime('%Y-%m-%d-%H%M')}.{ext}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Row builders — 共用於 CSV 與 PDF（PDF 第一列當表頭，後續為資料列）
# =============================================================================


def _kpi_to_rows(report: dict) -> list[list[str]]:
    """KPI 報表展平：funnel + dispute_rates + technician_efficiency。"""
    rows: list[list[str]] = [["section", "metric", "value"]]
    rows.append(["meta", "period", str(report.get("period", ""))])
    rows.append(["meta", "generated_at", str(report.get("generated_at", ""))])

    for k, v in (report.get("funnel") or {}).items():
        rows.append(["funnel", k, str(v)])

    for k, v in (report.get("dispute_rates") or {}).items():
        rows.append(["dispute_rates", k, "" if v is None else str(v)])

    eff = report.get("technician_efficiency") or {}
    for k, v in eff.items():
        rows.append(["technician_efficiency", k, "" if v is None else str(v)])

    return rows


def _revenue_to_rows(report: dict) -> list[list[str]]:
    """Revenue 展平：先列 KPI，再列月度趨勢，再列品牌占比。"""
    rows: list[list[str]] = [["section", "key", "value"]]
    rows.append(["meta", "granularity", str(report.get("granularity", ""))])

    for k, v in (report.get("kpis") or {}).items():
        rows.append(["kpis", k, "" if v is None else str(v)])

    rows.append([])
    rows.append(["trend", "month", "amount"])
    for point in report.get("trend") or []:
        rows.append(["trend", str(point.get("month", "")), str(point.get("amount", ""))])

    rows.append([])
    rows.append(["by_brand", "brand", "amount"])
    for point in report.get("by_brand") or []:
        rows.append(
            ["by_brand", str(point.get("brand", "")), str(point.get("amount", ""))]
        )

    return rows


def _technician_ranking_to_rows() -> list[list[str]]:
    """技師排行 placeholder — service 尚未實作，先回最小可用 row。"""
    return [
        ["technician_id", "name", "completed_orders", "avg_rating"],
        ["", "尚未實作技師排行 service，請待後續 endpoint 補上", "", ""],
    ]


def _accounting_to_rows(items: list[dict]) -> list[list[str]]:
    """結算報表展平：每筆 settlement 一列。"""
    rows: list[list[str]] = [
        [
            "settlement_id",
            "reconciliation_id",
            "technician_id",
            "technician_name",
            "amount",
            "currency",
            "status",
            "payment_method",
            "paid_at",
            "created_at",
        ]
    ]
    for it in items:
        rows.append(
            [
                str(it.get("id", "")),
                str(it.get("reconciliation_id", "")),
                str(it.get("technician_id", "")),
                str(it.get("technician_name", "")),
                str(it.get("amount", "")),
                str(it.get("currency", "")),
                str(it.get("status", "")),
                str(it.get("payment_method", "")),
                str(it.get("paid_at", "")),
                str(it.get("created_at", "")),
            ]
        )
    return rows


# =============================================================================
# Data fetch — 集中 service 呼叫；CSV/PDF 共享
# =============================================================================


async def _build_rows(
    *,
    tenant_id: str,
    report_type: str,
    period: str | None,
) -> tuple[list[list[str]], dict]:
    """回傳 (rows, meta)。meta 用於 PDF 標題顯示（例如 period / generated_at）。"""
    if report_type == "kpi":
        report = await kpi_service.get_kpi_report(
            tenant_id=tenant_id, period=period or "30d"
        )
        return _kpi_to_rows(report), {
            "title": "KPI 報表 (KPI Report)",
            "subtitle": f"period: {report.get('period', '')}",
        }

    if report_type == "revenue":
        report = await revenue_service.get_revenue_summary(tenant_id=tenant_id)
        return _revenue_to_rows(report), {
            "title": "營收報表 (Revenue Report)",
            "subtitle": f"granularity: {report.get('granularity', '')}",
        }

    if report_type == "technician_ranking":
        return _technician_ranking_to_rows(), {
            "title": "技師排行報表 (Technician Ranking)",
            "subtitle": "service 尚未實作，待後續 endpoint 補上",
        }

    if report_type == "accounting":
        result = await settlement_service.list_settlements(
            tenant_id=tenant_id,
            cursor=None,
            limit=_ACCOUNTING_EXPORT_LIMIT,
            status=None,
            technician_id=None,
        )
        items = result.get("items") or []
        return _accounting_to_rows(items), {
            "title": "結算報表 (Accounting / Settlements)",
            "subtitle": f"records: {len(items)}"
            + (" (truncated)" if result.get("has_more") else ""),
        }

    raise ApiError(
        "VALIDATION_ERROR",
        f"report_type must be one of {sorted(VALID_REPORT_TYPES)}",
        422,
    )


# =============================================================================
# CSV path
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
    rows, _meta = await _build_rows(
        tenant_id=tenant_id,
        report_type=report_type,
        period=period,
    )
    for row in rows:
        yield _csv_line(row)


# =============================================================================
# PDF path
# =============================================================================


_PDF_FONT_REGISTERED = False
_PDF_FONT_NAME = "STSong-Light"


def _ensure_pdf_font() -> None:
    """延遲註冊 CID 字型 — 與 voucher_service 同 pattern。"""
    global _PDF_FONT_REGISTERED
    if _PDF_FONT_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont(_PDF_FONT_NAME))
    _PDF_FONT_REGISTERED = True


def _render_pdf(rows: list[list[str]], meta: dict) -> bytes:
    """共用 PDF 渲染 — 第一列當表頭，後續資料列。

    rows 中允許空 list（CSV 的「空行分隔區塊」），PDF 渲染時跳過避免空 cell。
    """
    _ensure_pdf_font()

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title=meta.get("title", "Report"),
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base_styles["Title"],
        fontName=_PDF_FONT_NAME,
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=base_styles["Normal"],
        fontName=_PDF_FONT_NAME,
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=10,
    )
    footer_style = ParagraphStyle(
        "ReportFooter",
        parent=base_styles["Normal"],
        fontName=_PDF_FONT_NAME,
        fontSize=8,
        textColor=colors.grey,
        spaceBefore=8,
    )

    story: list = [
        Paragraph(meta.get("title", "Report"), title_style),
        Paragraph(meta.get("subtitle", ""), subtitle_style),
    ]

    # 拆分區塊：rows 中的空 list 視為區塊分隔（CSV 慣例），各區塊獨立成表
    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []
    for r in rows:
        if r:
            current.append(r)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    for i, block in enumerate(blocks):
        if i > 0:
            story.append(Spacer(1, 6 * mm))
        if not block:
            continue
        # block[0] 為表頭
        table = Table(block, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), _PDF_FONT_NAME, 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    story.append(
        Paragraph(
            f"Generated at {now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            footer_style,
        )
    )

    doc.build(story)
    return buf.getvalue()


async def render_pdf(
    *,
    tenant_id: str,
    report_type: str,
    period: str | None = None,
    from_date: str | None = None,  # noqa: ARG001 - 預留 future 使用
    to_date: str | None = None,    # noqa: ARG001
) -> bytes:
    """回傳完整 PDF bytes。"""
    rows, meta = await _build_rows(
        tenant_id=tenant_id,
        report_type=report_type,
        period=period,
    )
    return _render_pdf(rows, meta)


# =============================================================================
# Validation
# =============================================================================


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
    if report_type == "kpi" and period is not None:
        if period not in {"today", "7d", "30d", "90d"}:
            raise ApiError(
                "VALIDATION_ERROR",
                "period must be one of today/7d/30d/90d",
                422,
            )
