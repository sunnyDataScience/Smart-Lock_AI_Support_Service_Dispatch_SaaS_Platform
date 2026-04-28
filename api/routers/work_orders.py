"""WorkOrders router — 2 endpoints (read-only)。

operationId 對齊 openapi.yaml：
  listWorkOrders, getWorkOrder

寫入路徑（accept/complete/escalate/assign/reschedule）暫不實作，待寫入需求明確再開。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    DispatchQueueSnapshot,
    WorkOrder,
    WorkOrderEnvelope,
    WorkOrderPage,
)
from services import work_order_service

router = APIRouter()


@router.get(
    "/work-orders",
    operation_id="listWorkOrders",
    summary="工單列表（cursor 分頁）",
    response_model=WorkOrderPage,
)
async def list_work_orders(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await work_order_service.list_orders(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [WorkOrder(**w).model_dump(mode="json") for w in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/work-orders/dispatch-queue",
    operation_id="getDispatchQueue",
    summary="派工佇列快照（即時聚合）",
    response_model=DispatchQueueSnapshot,
)
async def get_dispatch_queue(
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """必須註冊在 /work-orders/{id} 之前，否則 'dispatch-queue' 會被當成 id。"""
    return await work_order_service.get_dispatch_queue_snapshot(
        tenant_id=user.tenant_id,
    )


@router.get(
    "/work-orders/{id}",
    operation_id="getWorkOrder",
    summary="工單詳情",
    response_model=WorkOrderEnvelope,
)
async def get_work_order(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    order = await work_order_service.get_order(
        tenant_id=user.tenant_id, wo_id=id,
    )
    return {"data": WorkOrder(**order).model_dump(mode="json")}
