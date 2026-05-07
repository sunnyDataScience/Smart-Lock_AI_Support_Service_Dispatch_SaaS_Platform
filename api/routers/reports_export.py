"""Reports export router — exportReport endpoint。

operationId 對齊 openapi.yaml：exportReport（KPI / 營收 / 技師排行 → CSV / PDF）

PDF 路徑現階段一律 422（缺 reportlab/weasyprint dep，不在本 task 範圍）；
CSV 串流以 generator 寫出，行內生成不囤 buffer。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from core.deps import CurrentUser, role_required
from services import report_export_service

logger = logging.getLogger("api.routers.reports_export")

router = APIRouter()


_export_role_gate = role_required("admin", "operations_manager", "accountant")


@router.get(
    "/reports/export",
    operation_id="exportReport",
    summary="匯出 KPI / 營收 / 技師排行報表（CSV / PDF）",
    responses={
        200: {
            "description": "CSV / PDF stream",
            "content": {"text/csv": {}, "application/pdf": {}},
        },
        403: {"description": "缺乏匯出權限"},
        422: {"description": "參數錯誤或 PDF 尚未實作"},
    },
)
async def export_report(
    report_type: str = Query(..., description="kpi / revenue / technician_ranking"),
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
