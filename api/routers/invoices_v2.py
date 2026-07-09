"""Invoices v2 router — tenant-scoped read-only（CR-0003 P2-W5 / FR-0011 read 側）。

對齊 frozen spec §2.2 M11 Invoice（read-only slice）：
  - GET  /tenants/{tenantId}/accounting/invoices          → listInvoicesV2 (cursor 分頁)
  - GET  /tenants/{tenantId}/accounting/invoices/{id}     → getInvoiceV2

NOTE：
  - 付款 / 開立側（createInvoice / voidInvoice / reissueInvoice）屬 FR-0011 draft + 金流未選，
    留 P3，本 slice 不做任何寫入端點。
  - 舊 flat 路徑 /api/v1/accounting/invoices（routers/invoices.py）仍保留，
    加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 invoice_service 函式，零重寫 SQL
  - read GET（無 idempotency）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import (
    Invoice,
    InvoiceEnvelope,
    InvoicePage,
    InvoiceStatus,
)
from services import invoice_service

router = APIRouter()

_BILLING_ROLES = ("admin", "operations_manager")  # SA-01：死角色移除


class _FromQuoteBody(BaseModel):
    quote_id: str = Field(..., description="來源報價（須為 accepted 狀態）")


@router.get(
    "/tenants/{tenantId}/accounting/invoices",
    operation_id="listInvoicesV2",
    summary="發票列表 v2（tenant-scoped，cursor 分頁）",
    response_model=InvoicePage,
    tags=["M11 Invoice"],
)
async def list_invoices_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: InvoiceStatus | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None, description="發票號碼模糊搜尋"),
    created_after: str | None = Query(default=None, description="建立時間下限 ISO 8601"),
    created_before: str | None = Query(default=None, description="建立時間上限 ISO 8601"),
    payment_method: str | None = Query(default=None, description="付款方式 (credit_card/bank_transfer/cash/line_pay/other)"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await invoice_service.list_invoices(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        work_order_id=work_order_id,
        keyword=keyword,
        created_after=created_after,
        created_before=created_before,
        payment_method=payment_method,
    )
    return {
        "items": [Invoice(**inv).model_dump(mode="json") for inv in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/tenants/{tenantId}/accounting/invoices/{id}",
    operation_id="getInvoiceV2",
    summary="發票詳情 v2（tenant-scoped）",
    response_model=InvoiceEnvelope,
    tags=["M11 Invoice"],
)
async def get_invoice_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    inv = await invoice_service.get_invoice(tenant_id=tenantId, invoice_id=id)
    return {"data": Invoice(**inv).model_dump(mode="json")}


@router.post(
    "/tenants/{tenantId}/accounting/invoices:from-quote",
    operation_id="createInvoiceFromQuoteV2", status_code=201,
    summary="從 accepted 報價開立應收發票 v2（CR-0035；管理角色）",
    response_model=InvoiceEnvelope,
    tags=["M11 Invoice"],
)
async def create_invoice_from_quote_v2(
    body: _FromQuoteBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*_BILLING_ROLES, fail_closed=True)),
) -> dict:
    """後台手動補開應收發票（accept 自動開立失敗 / 需人工控管時）。

    冪等：work_order_id UNIQUE —— 同工單已有發票回既有（200 語意但回 201 + 既有 row）。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId does not match authenticated tenant", 403)
    inv = await invoice_service.create_from_quote(tenant_id=tenantId, quote_id=body.quote_id)
    return {"data": Invoice(**inv).model_dump(mode="json")}
