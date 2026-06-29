"""Customers v2 router — tenant-scoped 客戶主檔端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M04 Customer：
  - GET  /tenants/{tenantId}/customers          → listCustomers (cursor 分頁)
  - POST /tenants/{tenantId}/customers          → createCustomer
  - GET  /tenants/{tenantId}/customers/{id}     → getCustomer (聚合歷史)

舊 flat 路徑 /api/v1/customers（routers/customers.py）仍保留，
加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 customer_service 函式，不重寫 SQL
  - envelope：{ success, data } 對齊既有慣例
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import (
    Customer,
    CustomerCreateRequest,
    CustomerEnvelope,
    CustomerPage,
    CustomerUpdateRequest,
)
from services import customer_service

router = APIRouter()

_customer_writer = role_required("admin", "operations_manager")


@router.get(
    "/tenants/{tenantId}/customers",
    operation_id="listCustomersV2",
    summary="客戶主檔列表 v2（tenant-scoped，cursor 分頁）",
    response_model=CustomerPage,
    tags=["M04 Customer"],
)
async def list_customers_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None, description="風險等級 low/medium/high/critical"),
    device_brand: str | None = Query(default=None, description="主要設備品牌"),
    warranty_status: str | None = Query(default=None, description="保固狀態 active/expired/none"),
    preferred_technician_id: str | None = Query(default=None, description="偏好技師 UUID"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await customer_service.list_customers(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        risk_level=risk_level,
        device_brand=device_brand,
        warranty_status=warranty_status,
        preferred_technician_id=preferred_technician_id,
    )
    return {
        "items": [Customer(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


# 注意：本路由必須註冊在 GET /customers/{id} 之前，否則 "/customers/stats"
# 會被 {id} path param 吞掉（FastAPI 依註冊順序匹配）。
@router.get(
    "/tenants/{tenantId}/customers/stats",
    operation_id="customerStatsV2",
    summary="客戶主檔聚合統計 v2（活躍/高風險/已過保固，統計卡用）",
    tags=["M04 Customer"],
)
async def customer_stats_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    stats = await customer_service.customer_stats(tenant_id=tenantId)
    return {"data": stats}


@router.post(
    "/tenants/{tenantId}/customers",
    operation_id="createCustomerV2",
    summary="建立客戶 v2（tenant-scoped，admin / operations_manager；非 LINE 來源手動建檔）",
    response_model=CustomerEnvelope,
    status_code=201,
    tags=["M04 Customer"],
)
async def create_customer_v2(
    body: CustomerCreateRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(_customer_writer),
) -> JSONResponse:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    payload = body.model_dump(exclude_unset=True)
    customer = await customer_service.create_customer(
        tenant_id=tenantId, payload=payload
    )
    envelope = {
        "success": True,
        "data": Customer(**customer).model_dump(mode="json"),
    }
    return JSONResponse(status_code=201, content=envelope)


@router.get(
    "/tenants/{tenantId}/customers/{id}",
    operation_id="getCustomerV2",
    summary="客戶單筆詳情 v2（tenant-scoped，聚合歷史：工單統計 / 平均評分 / 投訴 / 退款 / 最近紀錄）",
    tags=["M04 Customer"],
)
async def get_customer_v2(
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

    return await customer_service.get_customer(
        tenant_id=tenantId, customer_id=id
    )


@router.put(
    "/tenants/{tenantId}/customers/{id}",
    operation_id="updateCustomerV2",
    summary="更新客戶資料 v2（tenant-scoped，admin / operations_manager；整體取代，未提供欄位視為 null）",
    response_model=CustomerEnvelope,
    tags=["M04 Customer"],
)
async def update_customer_v2(
    body: CustomerUpdateRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(_customer_writer),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    payload = body.model_dump()
    customer = await customer_service.update_customer(
        tenant_id=tenantId, customer_id=id, payload=payload
    )
    return {"success": True, "data": Customer(**customer).model_dump(mode="json")}
