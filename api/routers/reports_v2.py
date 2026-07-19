"""Reports v2 — tenant-scoped KPI / Revenue / Export（CR-0003 P2-W1, FR-0021）。

spec 對齊：
  GET /tenants/{tenantId}/reports/kpi        → getReportKpi
  GET /tenants/{tenantId}/reports/revenue    → getReportRevenue
  GET /tenants/{tenantId}/reports/export     → exportReport（CSV stream / PDF；UAT R3-9 補 format=pdf）

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 kpi_service / revenue_service / report_export_service，零重寫業務邏輯
  - 不改 legacy /api/v1 router
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response, StreamingResponse

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import DashboardPeriod, KpiReport, RevenueSummary
from services import kpi_service, report_export_service, revenue_service

router = APIRouter()

# export 端點沿用 legacy 相同的角色閘門（admin / operations_manager / accountant）
_export_role_gate = role_required("admin", "operations_manager", "accountant")


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/reports/kpi
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/reports/kpi",
    operation_id="getReportKpi",
    summary="KPI 儀表板（tenant-scoped v2；漏斗 / 異常率 / 技師效率；read-only）",
    response_model=KpiReport,
    tags=["Reports"],
)
async def get_report_kpi(
    tenantId: str = Path(...),
    period: DashboardPeriod = Query(default=DashboardPeriod.field_30d),
    start_date: date | None = Query(
        default=None,
        description="統計起日（含），與 end_date 搭配使用；提供時覆蓋 period。",
    ),
    end_date: date | None = Query(
        default=None,
        description="統計迄日（含），與 start_date 搭配使用；提供時覆蓋 period。",
    ),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    report = await kpi_service.get_kpi_report(
        tenant_id=tenantId,
        period=period.value,
        start_date=start_date,
        end_date=end_date,
    )
    return KpiReport(**report).model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/reports/revenue
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/reports/revenue",
    operation_id="getReportRevenue",
    summary="營收彙整（tenant-scoped v2；KPI + 月度趨勢 + 品牌占比）",
    response_model=RevenueSummary,
    tags=["Reports"],
)
async def get_report_revenue(
    tenantId: str = Path(...),
    granularity: str = Query(default="month"),
    start_date: date | None = Query(
        default=None,
        description="統計起日（含），落點以 invoices.issued_at 為準（draft 走 created_at）。",
    ),
    end_date: date | None = Query(
        default=None,
        description="統計迄日（含），與 start_date 搭配使用。",
    ),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    summary = await revenue_service.get_revenue_summary(
        tenant_id=tenantId,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )
    return RevenueSummary(**summary).model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/reports/export
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/reports/export",
    operation_id="exportReportV2",
    summary="匯出 KPI / 營收 / 技師排行 / 結算報表（tenant-scoped v2；CSV stream / PDF）",
    responses={
        200: {
            "description": "CSV / PDF stream",
            "content": {"text/csv": {}, "application/pdf": {}},
        },
        403: {"description": "缺乏匯出權限或跨 tenant 存取"},
        422: {"description": "參數錯誤"},
    },
    tags=["Reports"],
)
async def export_report_v2(
    tenantId: str = Path(...),
    report_type: str = Query(
        ..., description="kpi / revenue / technician_ranking / accounting"
    ),
    format: str = Query(default="csv", description="csv / pdf"),
    period: str | None = Query(default=None, description="KPI 期間：today/7d/30d/90d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: CurrentUser = Depends(_export_role_gate),
):
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # UAT R3-9：原本整個吞掉 format query param 恆走 CSV——前端選 PDF 拿到的
    # .pdf 內容其實是 CSV（打不開）。改對齊 legacy /api/v1/reports/export：
    # format=pdf 走 report_export_service.render_pdf（reportlab + STSong-Light）。
    report_export_service.validate_inputs(
        report_type=report_type, fmt=format, period=period
    )

    now = report_export_service.now_utc()

    if format == "pdf":
        pdf_bytes = await report_export_service.render_pdf(
            tenant_id=tenantId,
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
            tenant_id=tenantId,
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
