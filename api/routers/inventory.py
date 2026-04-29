"""Inventory router — read-only 庫存品項。

operationId 對齊 openapi.yaml：
  - listInventoryItems — cursor 分頁 + stock_status / category 過濾

未來擴充（不在本 phase 範圍）：
  - createInventoryItem / updateInventoryItem / deleteInventoryItem
  - createInventoryTransaction（補貨 / 出庫 / 退貨 / 調整）
  - getInventoryItem 詳情（InventoryItemEnvelope schema 已預留）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import InventoryItem, InventoryItemPage, InventoryStockStatus
from services import inventory_service

router = APIRouter()


@router.get(
    "/inventory/items",
    operation_id="listInventoryItems",
    summary="庫存品項清單（read-only；cursor 分頁 + 庫存狀態 / 類別過濾）",
    response_model=InventoryItemPage,
)
async def list_inventory_items(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    stock_status: InventoryStockStatus | None = Query(default=None),
    category: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await inventory_service.list_items(
        cursor=cursor,
        limit=limit,
        stock_status=stock_status.value if stock_status else None,
        category=category,
    )
    return {
        "items": [InventoryItem(**i).model_dump(mode="json") for i in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
