"""Dispatch router — listDispatchCandidates / autoMatchDispatch / assignDispatch。

operationId 對齊 openapi.yaml：
  listDispatchCandidates  GET  /dispatch/candidates
  autoMatchDispatch       POST /dispatch/auto-match
  assignDispatch          POST /dispatch/assign

listDispatchLogs 由 routers/dispatch_logs.py 維護。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant, role_required
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    DispatchAssignRequest,
    DispatchAutoMatchRequest,
    DispatchAutoMatchResponse,
    WorkOrder,
    WorkOrderEnvelope,
)
from services import audit_log_service, dispatch_service

# F-004 manual dispatch — 同 work_orders.py：admin/operations_manager/tenant_admin
# /dispatcher/customer_service 才能呼叫；客服繞過時強制 audit log。
_DISPATCH_ALLOWED_ROLES = (
    "admin",
    "operations_manager",
    "tenant_admin",
    "dispatcher",
    "customer_service",
)
_BYPASS_ROLES = {"customer_service"}

router = APIRouter()


@router.get(
    "/dispatch/candidates",
    operation_id="listDispatchCandidates",
    summary="查詢候選技師（A37 派工人工介入）",
)
async def list_dispatch_candidates(
    work_order_id: str = Query(...),
    skills: list[str] | None = Query(default=None),
    areas: list[str] | None = Query(default=None),
    levels: list[str] | None = Query(default=None),
    exclude_circuit: bool = Query(default=True),
    rating_min: float | None = Query(default=None, ge=0.0, le=5.0),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await dispatch_service.list_dispatch_candidates(
        tenant_id=user.tenant_id,
        work_order_id=work_order_id,
        skills_filter=skills,
        areas_filter=areas,
        levels_filter=levels,
        exclude_circuit=exclude_circuit,
        rating_min=rating_min,
    )


@router.post(
    "/dispatch/auto-match",
    operation_id="autoMatchDispatch",
    summary="依問題卡自動匹配候選技師（top-N）",
    response_model=DispatchAutoMatchResponse,
)
async def auto_match_dispatch(
    body: DispatchAutoMatchRequest,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    urgency_str = (
        body.urgency.value if body.urgency and hasattr(body.urgency, "value") else (body.urgency or "normal")
    )
    result = await dispatch_service.auto_match_dispatch(
        tenant_id=user.tenant_id,
        problem_card_id=str(body.problem_card_id),
        urgency=urgency_str,
        max_candidates=body.max_candidates or 3,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


@router.post(
    "/dispatch/assign",
    operation_id="assignDispatch",
    summary="批次/外部整合用 — body 帶 work_order_id 的工單指派",
    response_model=WorkOrderEnvelope,
)
async def assign_dispatch(
    body: DispatchAssignRequest,
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    order = await dispatch_service.assign_dispatch(
        tenant_id=user.tenant_id,
        work_order_id=str(body.work_order_id),
        technician_id=str(body.technician_id),
        override_reason=body.override_reason,
    )
    # PM Q6=A — 客服繞過自動派工必須留稽核軌跡
    if user.role in _BYPASS_ROLES:
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="manual_dispatch_bypass",
            target_type="work_order",
            target_id=str(body.work_order_id),
            payload={
                "endpoint": "assignDispatch",
                "technician_id": str(body.technician_id),
                "override_reason": body.override_reason or "未提供理由",
            },
        )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
