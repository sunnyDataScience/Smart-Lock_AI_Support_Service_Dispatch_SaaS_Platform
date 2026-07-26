"""Vouchers router — listVouchers + exportVoucher。

operationId 對齊 openapi.yaml：
  - listVouchers       GET /accounting/vouchers
  - exportVoucher      GET /accounting/vouchers/{id}/export → PDF
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from core.deps import REVIEW_ROLES, CurrentUser, role_required
from models.generated import Voucher, VoucherPage
from services import voucher_service

router = APIRouter()


@router.get(
    "/accounting/vouchers",
    operation_id="listVouchers",
    summary="會計傳票列表（cursor 分頁，可依 posting_date 區間過濾）",
    response_model=VoucherPage,
)
async def list_vouchers(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    posting_date_start: date | None = Query(default=None),
    posting_date_end: date | None = Query(default=None),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    page = await voucher_service.list_vouchers(
        tenant_id=user.tenant_id,
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
    "/accounting/vouchers/{voucher_id}/export",
    operation_id="exportVoucher",
    summary="匯出傳票 PDF（A4）",
    responses={
        200: {
            "description": "PDF 二進位",
            "content": {"application/pdf": {}},
        },
        404: {"description": "Voucher not found"},
    },
)
async def export_voucher(
    voucher_id: str,
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> Response:
    voucher = await voucher_service.get_voucher(
        tenant_id=user.tenant_id,
        voucher_id=voucher_id,
    )
    pdf_bytes = voucher_service.render_voucher_pdf(voucher)
    filename = f"voucher_{voucher.get('voucher_number') or voucher_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
