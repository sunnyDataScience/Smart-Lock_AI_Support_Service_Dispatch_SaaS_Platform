"""Reports export router — exportReport endpoint。

operationId 對齊 openapi.yaml：exportReport
  - report_type: kpi / revenue / technician_ranking / accounting
  - format: csv（行內 stream）/ pdf（reportlab，整檔生成後一次回傳）

CSV 串流以 generator 寫出，行內生成不囤 buffer。
PDF 採 reportlab + STSong-Light CID 字型（與 voucher_service 同 pattern）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse

from core.deps import CurrentUser, role_required
from services import report_export_service

logger = logging.getLogger("api.routers.reports_export")

router = APIRouter()


_export_role_gate = role_required("admin", "operations_manager", "accountant")


@router.get(
    "/reports/export",
    operation_id="exportReport",
    summary="匯出 KPI / 營收 / 技師排行 / 結算報表（CSV / PDF）",
    responses={
        200: {
            "description": "CSV / PDF stream",
            "content": {"text/csv": {}, "application/pdf": {}},
        },
        403: {"description": "缺乏匯出權限"},
        422: {"description": "參數錯誤"},
    },
)
async def export_report(
    report_type: str = Query(
        ..., description="kpi / revenue / technician_ranking / accounting"
    ),
    format: str = Query("csv", description="csv / pdf"),
    period: str | None = Query(default=None, description="KPI 期間：today/7d/30d/90d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: CurrentUser = Depends(_export_role_gate),
):
    report_export_service.validate_inputs(
        report_type=report_type, fmt=format, period=period
    )

    now = report_export_service.now_utc()

    if format == "pdf":
        pdf_bytes = await report_export_service.render_pdf(
            tenant_id=user.tenant_id,
            report_type=report_type,
            period=period,
            from_date=from_,
            to_date=to,
        )
        fname = report_export_service.filename(now, report_type, "pdf")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
            },
        )

    fname = report_export_service.filename(now, report_type, "csv")

    async def gen():
        async for line in report_export_service.stream_csv(
            tenant_id=user.tenant_id,
            report_type=report_type,
            period=period,
            from_date=from_,
            to_date=to,
        ):
            yield line

    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
        },
    )
