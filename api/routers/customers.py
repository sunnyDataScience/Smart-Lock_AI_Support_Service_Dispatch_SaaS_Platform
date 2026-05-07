"""Customers router — 客戶主檔（管理員視角）。

operationId 對齊 openapi.yaml：
  - listCustomers — tenant 內的 LINE 使用者，cursor 分頁，含對話 / 工單聚合計數
  - getCustomer  — 單筆詳情 + 聚合歷史
  - createCustomer — admin / operations_manager 手動建檔（非 LINE 來源）
  - updateCustomer — admin / operations_manager 整體取代（PUT 語意）

未來擴充：風險等級 / 滿意度 / 偏好技師 / 保固聚合（需獨立資料來源）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant, role_required
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
    "/customers",
    operation_id="listCustomers",
    summary="客戶主檔列表（管理員視角，cursor 分頁）",
    response_model=CustomerPage,
)
async def list_customers(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await customer_service.list_customers(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [Customer(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/customers",
    operation_id="createCustomer",
    summary="建立客戶（admin / operations_manager；非 LINE 來源手動建檔）",
    response_model=CustomerEnvelope,
    status_code=201,
)
async def create_customer(
    body: CustomerCreateRequest,
    user: CurrentUser = Depends(_customer_writer),
) -> JSONResponse:
    payload = body.model_dump(exclude_unset=True)
    customer = await customer_service.create_customer(
        tenant_id=user.tenant_id, payload=payload
    )
    envelope = {
        "success": True,
        "data": Customer(**customer).model_dump(mode="json"),
    }
    return JSONResponse(status_code=201, content=envelope)


@router.get(
    "/customers/{id}",
    operation_id="getCustomer",
    summary="客戶單筆詳情 + 聚合歷史（工單統計 / 平均評分 / 投訴 / 退款 / 最近紀錄）",
)
async def get_customer(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await customer_service.get_customer(
        tenant_id=user.tenant_id, customer_id=id
    )


@router.put(
    "/customers/{id}",
    operation_id="updateCustomer",
    summary="更新客戶資料（admin / operations_manager；整體取代，未提供欄位視為 null）",
    response_model=CustomerEnvelope,
)
async def update_customer(
    body: CustomerUpdateRequest,
    id: str = Path(),
    user: CurrentUser = Depends(_customer_writer),
) -> dict:
    payload = body.model_dump()
    customer = await customer_service.update_customer(
        tenant_id=user.tenant_id, customer_id=id, payload=payload
    )
    return {"success": True, "data": Customer(**customer).model_dump(mode="json")}
