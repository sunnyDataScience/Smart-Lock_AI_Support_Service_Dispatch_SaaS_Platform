"""Customers router — read-only 客戶主檔（管理員視角）。

operationId 對齊 openapi.yaml：
  - listCustomers — tenant 內的 LINE 使用者，cursor 分頁，含對話 / 工單聚合計數

未來擴充（不在本 phase 範圍）：
  - getCustomer：單筆詳情（CustomerEnvelope schema 已預留）
  - 風險等級 / 滿意度 / 偏好技師 / 保固聚合 — 需獨立資料來源
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import Customer, CustomerPage
from services import customer_service

router = APIRouter()


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
