"""WorkOrders Ops v2 router — operational 雜項 tenant-scoped 端點（CR-0003 P2-W4）。

對齊 frozen spec §M07 WorkOrder Ops（reschedule / delay / material-request / events / pool / dispatch-queue）：

  reschedule 家族：
    POST /tenants/{tenantId}/work-orders/{id}/reschedule-request   → requestRescheduleV2
    POST /tenants/{tenantId}/work-orders/{id}/reschedule:approve   → approveRescheduleV2

  延遲通知：
    POST /tenants/{tenantId}/work-orders/{id}/notify-delay         → notifyDelayV2

  缺料回報：
    POST /tenants/{tenantId}/work-orders/{id}/material-request     → recordMaterialRequestV2

  subflow 事件流水線：
    GET  /tenants/{tenantId}/work-orders/{id}/events               → listWorkOrderEventsV2

  案件池 / 派工佇列：
    GET  /tenants/{tenantId}/work-orders/pool                      → listWorkOrderPoolV2
    GET  /tenants/{tenantId}/dispatch/queue                        → getDispatchQueueV2

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - POST 走 idempotency_guard
  - 呼既有 work_order_service，零業務邏輯重寫
  - response_model 型別對齊 service 輸出（W1 教訓）
  - legacy /api/v1 路由不動（雙掛過渡）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    DispatchQueueSnapshot,
    WorkOrder,
    WorkOrderEnvelope,
    WorkOrderPage,
)
from services import work_order_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Role guards（對齊 work_order_actions.py 的 legacy 定義）
# ---------------------------------------------------------------------------

_tech_or_admin = role_required("technician", "admin", "operations_manager", "tenant_admin")
_admin_only = role_required("admin", "operations_manager", "tenant_admin")


# ---------------------------------------------------------------------------
# Cross-tenant guards（共用 helper，對齊 work_orders_v2.py）
# ---------------------------------------------------------------------------


def _cross_tenant_read(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )


def _cross_tenant_write(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )


# ---------------------------------------------------------------------------
# Request schemas（對齊 legacy work_order_actions.py）
# ---------------------------------------------------------------------------


class _RequestRescheduleBodyV2(BaseModel):
    new_scheduled_at: datetime = Field(..., description="ISO 8601 future datetime")
    reason: str = Field(..., min_length=1, max_length=500)


class _ApproveRescheduleBodyV2(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


class _NotifyDelayBodyV2(BaseModel):
    delay_minutes: int = Field(..., ge=5, le=300)
    reason: str = Field(..., min_length=1, max_length=500)


class _MaterialItemV2(BaseModel):
    brand: str = Field(..., min_length=1, max_length=40)
    model: str = Field(..., min_length=1, max_length=80)
    quantity: int = Field(..., ge=1, le=999)


class _MaterialRequestBodyV2(BaseModel):
    """T6 缺料回報（對齊 legacy _MaterialRequestBody）。"""

    items: list[_MaterialItemV2] = Field(..., min_length=1, max_length=20)
    urgency: Literal["now", "today", "tomorrow"] = "today"
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Pool / Dispatch-queue（GET，須在 /{id} 路由前）
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/work-orders/pool",
    operation_id="listWorkOrderPoolV2",
    summary="技師案件池 v2（tenant-scoped，可接工單，依 urgency + 建立時間排序）",
    response_model=WorkOrderPage,
    tags=["M07 WorkOrder Ops"],
)
async def list_work_order_pool_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    page = await work_order_service.list_work_order_pool(
        tenant_id=tenantId,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return {
        "items": [WorkOrder(**w).model_dump(mode="json") for w in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/tenants/{tenantId}/dispatch/queue",
    operation_id="getDispatchQueueV2",
    summary="派工佇列快照 v2（tenant-scoped，即時聚合）",
    response_model=DispatchQueueSnapshot,
    tags=["M07 WorkOrder Ops"],
)
async def get_dispatch_queue_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    return await work_order_service.get_dispatch_queue_snapshot(tenant_id=tenantId)


# ---------------------------------------------------------------------------
# Reschedule 家族
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/reschedule-request",
    operation_id="requestRescheduleV2",
    summary="技師 / 管理員直接改約 v2（tenant-scoped，單方變更，附 LINE 通知）",
    tags=["M07 WorkOrder Ops"],
)
async def request_reschedule_v2(
    body: _RequestRescheduleBodyV2,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(_tech_or_admin),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.request_reschedule(
        tenant_id=tenantId,
        wo_id=id,
        new_scheduled_at=body.new_scheduled_at.isoformat(),
        reason=body.reason,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/reschedule:approve",
    operation_id="approveRescheduleV2",
    summary="管理員核准 / 退回改約申請 v2（tenant-scoped）",
    tags=["M07 WorkOrder Ops"],
)
async def approve_reschedule_v2(
    body: _ApproveRescheduleBodyV2,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(_admin_only),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.approve_reschedule(
        tenant_id=tenantId,
        wo_id=id,
        decision=body.decision,
        comment=body.comment,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


# ---------------------------------------------------------------------------
# 延遲通知
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/notify-delay",
    operation_id="notifyDelayV2",
    summary="技師現場延遲 v2（tenant-scoped，主動 LINE 通知客戶）",
    tags=["M07 WorkOrder Ops"],
)
async def notify_delay_v2(
    body: _NotifyDelayBodyV2,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(_tech_or_admin),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.notify_delay(
        tenant_id=tenantId,
        wo_id=id,
        delay_minutes=body.delay_minutes,
        reason=body.reason,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


# ---------------------------------------------------------------------------
# 缺料回報
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/material-request",
    operation_id="recordMaterialRequestV2",
    summary="記錄缺料回報 v2（tenant-scoped，T6；技師作業中→等待調度員補料）",
    response_model=WorkOrderEnvelope,
    tags=["M07 WorkOrder Ops"],
)
async def record_material_request_v2(
    body: _MaterialRequestBodyV2,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.record_material_request(
        tenant_id=tenantId,
        wo_id=id,
        items=[item.model_dump() for item in body.items],
        urgency=body.urgency,
        note=body.note,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# 結構化事件流水線（GET）
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/work-orders/{id}/events",
    operation_id="listWorkOrderEventsV2",
    summary="列出工單結構化事件 v2（tenant-scoped，subflow timeline）",
    tags=["M07 WorkOrder Ops"],
)
async def list_work_order_events_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    event_type: Literal[
        "scope_change",
        "material_request",
        "delay",
        "door_check",
        "signature_submitted",
        "reschedule_proposed",
        "other",
    ]
    | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    return await work_order_service.list_work_order_events(
        tenant_id=tenantId,
        wo_id=id,
        event_type=event_type,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Flow 4 admin 補料管理彙整視圖（跨工單列出活躍的缺料回報）
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/material-requests",
    operation_id="listPendingMaterialRequestsV2",
    summary="跨工單列出活躍的缺料回報 v2（Flow 4 admin 補料管理彙整視圖）",
    tags=["M07 WorkOrder Ops"],
)
async def list_pending_material_requests_v2(
    tenantId: str = Path(...),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """跨工單列出近期 material_request 事件（排除 completed/confirmed/cancelled WO）。

    排序：urgency (now > today > tomorrow) → created_at DESC。
    每 row 含 event_id / payload (items[], urgency, note) / work_order_id / wo_status /
    scheduled_at / technician_id / actor_user_id（subflow actor_user_id 鏈路 per fix CR）。
    MVP 不分 pending vs supplied；admin 進工單詳情頁進一步處理。
    """
    _cross_tenant_read(user, tenantId)

    return await work_order_service.list_pending_material_requests(
        tenant_id=tenantId,
        limit=limit,
    )


class _MarkMaterialSuppliedBodyV2(BaseModel):
    """admin 標記補料完成 body。"""

    note: str | None = Field(default=None, max_length=500, description="補料完成備註")


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/material-request/{eventId}:supplied",
    operation_id="markMaterialRequestSuppliedV2",
    summary="標記某筆 material_request 已補料完成 v2（Flow 4 admin 收尾）",
    tags=["M07 WorkOrder Ops"],
)
async def mark_material_request_supplied_v2(
    body: _MarkMaterialSuppliedBodyV2,
    tenantId: str = Path(...),
    id: str = Path(..., description="work order id"),
    eventId: str = Path(..., description="material_request event id"),
    user: CurrentUser = Depends(_admin_only),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """admin 標記某筆 material_request 已補料完成（寫 supply_arrived 事件 + WS publish）。

    404 EVENT_NOT_FOUND / 422 INVALID_EVENT_TYPE / 422 EVENT_WO_MISMATCH /
    409 DUP_SUPPLY。
    """
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.mark_material_request_supplied(
        tenant_id=tenantId,
        wo_id=id,
        material_request_event_id=eventId,
        supplied_by_user_id=user.user_id,
        note=body.note,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CR-0007 reschedule:propose v2（多時段提案，獨立表 HD-04；slots 1-3 HD-02；
#                                 SLA 24h HD-03 由 DB 預設兜底）
# ─────────────────────────────────────────────────────────────────────────────


class _ProposedSlot(BaseModel):
    """單一時段，service 層接受 dict，僅做欄位提示。"""

    start: str = Field(..., description="ISO 8601 timestamp")
    end: str | None = Field(default=None, description="ISO 8601 timestamp（選填）")


class _ProposeRescheduleV2Body(BaseModel):
    """CR-0007 HD-02=(a) slots 1-3；DB CHECK 兜底，service 層先驗。"""

    proposed_slots: list[_ProposedSlot] = Field(
        ..., min_length=1, max_length=3, description="1-3 個提案時段"
    )
    message_to_customer: str | None = Field(default=None, max_length=500)
    send_via: Literal["line", "sms", "email"] = Field(default="line")


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/reschedule:propose",
    operation_id="proposeRescheduleV2",
    summary="多時段改約提案 v2（CR-0007 / 寫 saas.reschedule_proposal 獨立表 / SLA 24h / LINE Flex RSVP）",
    status_code=201,
    tags=["M07 WorkOrder Ops"],
)
async def propose_reschedule_v2(
    body: _ProposeRescheduleV2Body,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(_tech_or_admin),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """CR-0007 多時段改約提案：寫 saas.reschedule_proposal + (LINE Flex 由背景流處理)。"""
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.propose_reschedule_v2(
        tenant_id=tenantId,
        wo_id=id,
        proposed_slots=[s.model_dump(exclude_none=True) for s in body.proposed_slots],
        message_to_customer=body.message_to_customer,
        send_via=body.send_via,
        proposed_by_user_id=user.user_id,
        proposed_by_role=user.role,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# CR-0009 customer reschedule confirm/reject v2（admin JWT path，agent 呼叫用）
# HD-01=(a) /consumer/work-orders/{token}/... 是 future consumer browser flow；
#   本兩 endpoint 是 admin-side（tenant-scoped + JWT），agent flow 用
# ─────────────────────────────────────────────────────────────────────────────


class _CustomerRescheduleConfirmBody(BaseModel):
    selected_start: str = Field(..., description="ISO 8601 datetime")
    selected_end: str = Field(..., description="ISO 8601 datetime")


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/reschedule:customer-confirm",
    operation_id="confirmCustomerRescheduleV2",
    summary="客戶 LINE Flex 選定改期時段 v2（CR-0009；admin JWT；agent 呼叫）",
    tags=["M07 WorkOrder Ops"],
)
async def confirm_customer_reschedule_v2(
    body: _CustomerRescheduleConfirmBody,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.confirm_reschedule_by_customer(
        tenant_id=tenantId,
        wo_id=id,
        selected_start=body.selected_start,
        selected_end=body.selected_end,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/reschedule:customer-reject",
    operation_id="rejectCustomerRescheduleV2",
    summary="客戶 LINE Flex 點都不方便 v2（CR-0009；admin JWT；agent 呼叫）",
    tags=["M07 WorkOrder Ops"],
)
async def reject_customer_reschedule_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.reject_reschedule_by_customer(
        tenant_id=tenantId, wo_id=id,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
