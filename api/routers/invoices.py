"""Invoices router — listInvoices + getInvoice (read-only)。

operationId 對齊 openapi.yaml：listInvoices, getInvoice

不含 createInvoice / voidInvoice / reissueInvoice 等寫入路徑。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import REVIEW_ROLES, CurrentUser, require_tenant, role_required
from models.generated import (
    Invoice,
    InvoiceEnvelope,
    InvoicePage,
    InvoiceStatus,
)
from services import invoice_service

router = APIRouter()


@router.get(
    "/accounting/invoices",
    operation_id="listInvoices",
    summary="發票列表（cursor 分頁）",
    response_model=InvoicePage,
)
async def list_invoices(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: InvoiceStatus | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    page = await invoice_service.list_invoices(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        work_order_id=work_order_id,
    )
    return {
        "items": [Invoice(**inv).model_dump(mode="json") for inv in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/accounting/invoices/{id}",
    operation_id="getInvoice",
    summary="發票詳情",
    response_model=InvoiceEnvelope,
)
async def get_invoice(
    id: str,
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> dict:
    inv = await invoice_service.get_invoice(tenant_id=user.tenant_id, invoice_id=id)
    return {"data": Invoice(**inv).model_dump(mode="json")}
