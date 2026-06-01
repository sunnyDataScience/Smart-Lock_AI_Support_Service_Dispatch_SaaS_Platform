"""Vouchers v2 router — tenant-scoped 傳票端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M17 Voucher：
  - GET  /tenants/{tenantId}/vouchers          → listVouchersV2 (cursor 分頁 + posting_date 過濾)
  - GET  /tenants/{tenantId}/vouchers/{id}/export → exportVoucherV2 (PDF)

NOTE：
  - void（紅字沖銷）屬 P3，本 slice 不做。
  - 舊 flat 路徑 /api/v1/accounting/vouchers（routers/vouchers.py）仍保留，
    加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 voucher_service 函式，不重寫 SQL
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from models.generated import Voucher, VoucherPage
from services import voucher_service

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/vouchers",
    operation_id="listVouchersV2",
    summary="會計傳票列表 v2（tenant-scoped，cursor 分頁 + posting_date 區間過濾）",
    response_model=VoucherPage,
    tags=["M17 Voucher"],
)
async def list_vouchers_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    posting_date_start: date | None = Query(default=None),
    posting_date_end: date | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await voucher_service.list_vouchers(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        posting_date_start=posting_date_start,
        posting_date_end=posting_date_end,
    )
    return {
        "items": [Voucher(**v).model_dump(mode="json") for v in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/tenants/{tenantId}/vouchers/{id}/export",
    operation_id="exportVoucherV2",
    summary="匯出傳票 PDF v2（tenant-scoped，A4）",
    tags=["M17 Voucher"],
    responses={
        200: {
            "description": "PDF 二進位",
            "content": {"application/pdf": {}},
        },
        403: {"description": "Cross-tenant access denied"},
        404: {"description": "Voucher not found"},
    },
)
async def export_voucher_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    voucher = await voucher_service.get_voucher(
        tenant_id=tenantId,
        voucher_id=id,
    )
    pdf_bytes = voucher_service.render_voucher_pdf(voucher)
    filename = f"voucher_{voucher.get('voucher_number') or id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
