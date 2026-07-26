"""Customers router — 客戶主檔（管理員視角）。

operationId 對齊 openapi.yaml：
  - listCustomers — tenant 內的 LINE 使用者，cursor 分頁，含對話 / 工單聚合計數
  - getCustomer  — 單筆詳情 + 聚合歷史
  - createCustomer — admin / operations_manager 手動建檔（非 LINE 來源）
  - updateCustomer — admin / operations_manager 整體取代（PUT 語意）

未來擴充：風險等級 / 滿意度 / 偏好技師 / 保固聚合（需獨立資料來源）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response
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
    summary="客戶主檔列表（管理員視角，cursor 分頁）[DEPRECATED — 請遷移至 /tenants/{tenantId}/customers]",
    response_model=CustomerPage,
)
async def list_customers(
    response: Response,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    # CR-0183 補漏（2026-07-27）：legacy 端點原僅 require_tenant，v2 孿生已上守衛
    # → 低權限角色改打 /api/v1/customers 即可繞過。對齊 v2 與 rolePolicy。
    user: CurrentUser = Depends(role_required("admin", "operations_manager", "customer_service")),
) -> dict:
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        f"</tenants/{user.tenant_id}/customers>; rel=\"successor-version\""
    )
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
    summary="建立客戶（admin / operations_manager；非 LINE 來源手動建檔）[DEPRECATED — 請遷移至 /tenants/{tenantId}/customers]",
    response_model=CustomerEnvelope,
    status_code=201,
)
async def create_customer(
    body: CustomerCreateRequest,
    response: Response,
    user: CurrentUser = Depends(_customer_writer),
) -> JSONResponse:
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    # 注意：JSONResponse 直接回傳時需手動加 header（response 物件用於中間件注入）
    payload = body.model_dump(exclude_unset=True)
    customer = await customer_service.create_customer(
        tenant_id=user.tenant_id, payload=payload
    )
    envelope = {
        "success": True,
        "data": Customer(**customer).model_dump(mode="json"),
    }
    json_resp = JSONResponse(status_code=201, content=envelope)
    json_resp.headers["Deprecation"] = "true"
    json_resp.headers["Link"] = (
        f"</tenants/{user.tenant_id}/customers>; rel=\"successor-version\""
    )
    return json_resp


@router.get(
    "/customers/{id}",
    operation_id="getCustomer",
    summary="客戶單筆詳情 + 聚合歷史（工單統計 / 平均評分 / 投訴 / 退款 / 最近紀錄）[DEPRECATED — 請遷移至 /tenants/{tenantId}/customers/{id}]",
)
async def get_customer(
    response: Response,
    id: str = Path(),
    # CR-0183 補漏（2026-07-27）：同上，對齊 v2 GET /tenants/{tid}/customers/{id}。
    user: CurrentUser = Depends(role_required("admin", "operations_manager", "customer_service")),
) -> dict:
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        f"</tenants/{user.tenant_id}/customers/{id}>; rel=\"successor-version\""
    )
    return await customer_service.get_customer(
        tenant_id=user.tenant_id, customer_id=id
    )


@router.put(
    "/customers/{id}",
    operation_id="updateCustomer",
    summary="更新客戶資料（admin / operations_manager；整體取代，未提供欄位視為 null）[DEPRECATED]",
    response_model=CustomerEnvelope,
)
async def update_customer(
    body: CustomerUpdateRequest,
    response: Response,
    id: str = Path(),
    user: CurrentUser = Depends(_customer_writer),
) -> dict:
    # D3：雙掛過渡期 Deprecation header（CR-0002-α）
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        f"</tenants/{user.tenant_id}/customers/{id}>; rel=\"successor-version\""
    )
    payload = body.model_dump()
    customer = await customer_service.update_customer(
        tenant_id=user.tenant_id, customer_id=id, payload=payload
    )
    return {"success": True, "data": Customer(**customer).model_dump(mode="json")}
