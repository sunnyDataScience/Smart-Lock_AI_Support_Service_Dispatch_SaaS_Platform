"""Vouchers router — listVouchers endpoint。

operationId 對齊 openapi.yaml：listVouchers
exportVoucher 留待 PDF 渲染模組接入。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
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
    user: CurrentUser = Depends(require_tenant),
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
