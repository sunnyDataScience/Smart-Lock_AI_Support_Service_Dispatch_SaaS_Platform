"""WorkOrders router — read endpoints + 3 state-machine writes。

operationId 對齊 openapi.yaml：
  listWorkOrders, getWorkOrder, getDispatchQueue,
  acceptWorkOrder, completeWorkOrder, cancelWorkOrder

未實作：assignWorkOrder / escalateWorkOrder / proposeReschedule /
submitWorkOrderSignature / confirmWorkOrder（依賴技師 AI 推薦、SLA 模組
或上傳服務，待後續 phase）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    CompletionReport,
    DispatchQueueSnapshot,
    WorkOrder,
    WorkOrderCancelRequest,
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
    problem_card_id: str | None = Query(default=None, description="過濾特定問題卡的工單"),
    technician_id: str | None = Query(default=None, description="過濾特定技師的工單"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await work_order_service.list_orders(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        problem_card_id=problem_card_id,
        technician_id=technician_id,
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


@router.post(
    "/work-orders/{id}/accept",
    operation_id="acceptWorkOrder",
    summary="技師接單（assigned → accepted）",
    response_model=WorkOrderEnvelope,
)
async def accept_work_order(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await work_order_service.accept_order(
        tenant_id=user.tenant_id, wo_id=id,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/work-orders/{id}/complete",
    operation_id="completeWorkOrder",
    summary="完工回報（accepted | in_progress → completed）",
    response_model=WorkOrderEnvelope,
)
async def complete_work_order(
    body: CompletionReport,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await work_order_service.complete_order(
        tenant_id=user.tenant_id,
        wo_id=id,
        summary=body.summary,
        actual_amount=body.actual_amount,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/work-orders/{id}/cancel",
    operation_id="cancelWorkOrder",
    summary="取消工單（非結案 → cancelled）",
    response_model=WorkOrderEnvelope,
)
async def cancel_work_order(
    id: str = Path(),
    body: WorkOrderCancelRequest | None = None,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await work_order_service.cancel_order(
        tenant_id=user.tenant_id,
        wo_id=id,
        reason=body.reason if body else None,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
