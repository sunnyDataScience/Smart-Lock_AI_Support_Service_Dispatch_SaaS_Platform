"""WorkOrders router — read endpoints + 8 state-machine writes。

operationId 對齊 openapi.yaml：
  listWorkOrders, getWorkOrder, getDispatchQueue, listWorkOrderPool,
  acceptWorkOrder, assignWorkOrder, escalateWorkOrder,
  completeWorkOrder, cancelWorkOrder, confirmWorkOrder,
  submitWorkOrderSignature, proposeReschedule
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    ApiResponseGeneric,
    CompletionReport,
    DispatchQueueSnapshot,
    SignaturePayload,
    WorkOrder,
    WorkOrderAssignRequest,
    WorkOrderCancelRequest,
    WorkOrderConfirmRequest,
    WorkOrderEnvelope,
    WorkOrderEscalateRequest,
    WorkOrderPage,
)
from services import signature_service, work_order_service


class _RescheduleSlot(BaseModel):
    start: datetime
    end: datetime


class _ProposeRescheduleRequest(BaseModel):
    """Inline schema — openapi.yaml /work-orders/{id}/reschedule body。"""

    proposed_slots: list[_RescheduleSlot] = Field(..., min_length=1, max_length=3)
    message_to_customer: str = Field(..., max_length=120)
    warning_acknowledged_at: datetime | None = None
    send_via: Literal["line", "line_and_sms"] = "line"

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
    "/work-orders/pool",
    operation_id="listWorkOrderPool",
    summary="技師案件池（可接工單，依 urgency + 建立時間排序）",
    response_model=WorkOrderPage,
)
async def list_work_order_pool(
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """必須註冊在 /work-orders/{id} 之前，否則 'pool' 會被當成 id。"""
    page = await work_order_service.list_work_order_pool(
        tenant_id=user.tenant_id,
    )
    return {
        "items": [WorkOrder(**w).model_dump(mode="json") for w in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


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
    "/work-orders/{id}/assign",
    operation_id="assignWorkOrder",
    summary="手動指派技師（created | assigned → assigned）",
    response_model=WorkOrderEnvelope,
)
async def assign_work_order(
    body: WorkOrderAssignRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await work_order_service.assign_order(
        tenant_id=user.tenant_id,
        wo_id=id,
        technician_id=str(body.technician_id),
        reason_code=body.reason_code.value if hasattr(body.reason_code, "value") else str(body.reason_code),
        reason_text=body.reason_text,
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


@router.post(
    "/work-orders/{id}/confirm",
    operation_id="confirmWorkOrder",
    summary="客戶確認結案（completed → confirmed），寫入評分與意見",
    response_model=WorkOrderEnvelope,
)
async def confirm_work_order(
    body: WorkOrderConfirmRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await work_order_service.confirm_order(
        tenant_id=user.tenant_id,
        wo_id=id,
        rating=int(body.rating),
        feedback=body.feedback,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/work-orders/{id}/escalate",
    operation_id="escalateWorkOrder",
    summary="升級工單至 operations_manager / tenant_admin（不切狀態）",
    response_model=WorkOrderEnvelope,
)
async def escalate_work_order(
    body: WorkOrderEscalateRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    level_str = body.level.value if hasattr(body.level, "value") else str(body.level)
    order = await work_order_service.escalate_order(
        tenant_id=user.tenant_id,
        wo_id=id,
        level=level_str,
        reason=body.reason,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/work-orders/{id}/signature",
    operation_id="submitWorkOrderSignature",
    summary="雙方電子簽章（強制 Idempotency-Key）",
    response_model=ApiResponseGeneric,
)
async def submit_work_order_signature(
    body: SignaturePayload,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    result = await signature_service.submit_work_order_signature(
        tenant_id=user.tenant_id,
        wo_id=id,
        customer_signature=body.customer_signature,
        technician_signature=body.technician_signature,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
        signed_at=body.signed_at.isoformat() if body.signed_at else None,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


@router.post(
    "/work-orders/{id}/reschedule",
    operation_id="proposeReschedule",
    summary="送出改期請求（assigned | accepted | in_progress → 更新 scheduled_at）",
    response_model=WorkOrderEnvelope,
)
async def propose_reschedule(
    body: _ProposeRescheduleRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    slots = [
        {"start": s.start.isoformat(), "end": s.end.isoformat()}
        for s in body.proposed_slots
    ]
    order = await work_order_service.propose_reschedule(
        tenant_id=user.tenant_id,
        wo_id=id,
        proposed_slots=slots,
        message_to_customer=body.message_to_customer,
        send_via=body.send_via,
        warning_acknowledged_at=body.warning_acknowledged_at.isoformat()
        if body.warning_acknowledged_at
        else None,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
