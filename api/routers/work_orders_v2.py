"""WorkOrders v2 router — tenant-scoped 工單核心生命週期端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.3 M06 WorkOrder（核心生命週期）：
  - GET  /tenants/{tenantId}/work-orders              → listWorkOrdersV2 (cursor 分頁)
  - POST /tenants/{tenantId}/work-orders              → createWorkOrderV2 (from problem card)
  - GET  /tenants/{tenantId}/work-orders/{id}         → getWorkOrderV2

工單狀態機動作（tenant-scoped）：
  - POST /tenants/{tenantId}/work-orders/{id}:assign  → assignWorkOrderV2
  - POST /tenants/{tenantId}/work-orders/{id}:accept  → acceptWorkOrderV2
  - POST /tenants/{tenantId}/work-orders/{id}:complete → completeWorkOrderV2
  - POST /tenants/{tenantId}/work-orders/{id}:confirm → confirmWorkOrderV2
  - POST /tenants/{tenantId}/work-orders/{id}:escalate → escalateWorkOrderV2

進階 lifecycle（含簽章）：
  - POST /tenants/{tenantId}/work-orders/{id}/signature → submitWorkOrderSignatureV2
  - POST /tenants/{tenantId}/work-orders/{id}/scope-change → recordScopeChangeV2

取消：已由 P1-A /tenants/{tid}/work-orders/{id}/cancel 完成 → 不在此處理。

Operational 雜項（reschedule / delay / material-request / door-check 等）
保留 legacy /api/v1 路由（C-11，middleware 已蓋 Deprecation）。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 work_order_service / signature_service / audit_log_service 函式，零業務邏輯重寫
  - POST 端點走 idempotency_guard（需帶 Idempotency-Key header）
  - 雙掛過渡：舊 /api/v1/work-orders 保留，不改
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    ApiResponseGeneric,
    CompletionReport,
    SignaturePayload,
    WorkOrder,
    WorkOrderAssignRequest,
    WorkOrderConfirmRequest,
    WorkOrderEnvelope,
    WorkOrderEscalateRequest,
    WorkOrderPage,
)
from services import audit_log_service, signature_service, work_order_service

router = APIRouter()

# F-004 manual dispatch — 允許角色（與 legacy 對齊）
_DISPATCH_ALLOWED_ROLES = (
    "admin",
    "operations_manager",
    "tenant_admin",
    "dispatcher",
    "customer_service",
)
_BYPASS_ROLES = {"customer_service"}


# ---------------------------------------------------------------------------
# Request schemas（v2 新增）
# ---------------------------------------------------------------------------


class WorkOrderCreateRequest(BaseModel):
    """從已確認 ProblemCard 建立 WorkOrder（F-002 客服審 PC → 開 WO）。"""

    problem_card_id: str = Field(..., description="已確認的 ProblemCard UUID")
    customer_address: str | None = Field(default=None, max_length=300, description="服務地址（優先；缺省用 user profile）")
    customer_name: str | None = Field(default=None, max_length=80)
    customer_phone: str | None = Field(default=None, max_length=30)


class _ScopeItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    unit_price: str = Field(..., max_length=20)
    quantity: int = Field(..., ge=1, le=999)


class _ScopeChangeRequest(BaseModel):
    """T5 範圍變更申請。"""

    reason: str = Field(..., min_length=10, max_length=500)
    items: list[_ScopeItem] = Field(..., min_length=1, max_length=20)
    total_estimate: str | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# Helper
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
# READ endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/work-orders",
    operation_id="listWorkOrdersV2",
    summary="工單列表 v2（tenant-scoped，cursor 分頁）",
    response_model=WorkOrderPage,
    tags=["M06 WorkOrder"],
)
async def list_work_orders_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    problem_card_id: str | None = Query(default=None, description="過濾特定問題卡的工單"),
    technician_id: str | None = Query(default=None, description="過濾特定技師的工單"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    page = await work_order_service.list_orders(
        tenant_id=tenantId,
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
    "/tenants/{tenantId}/work-orders/{id}",
    operation_id="getWorkOrderV2",
    summary="工單詳情 v2（tenant-scoped）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def get_work_order_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    order = await work_order_service.get_order(
        tenant_id=tenantId, wo_id=id,
    )
    return {"data": WorkOrder(**order).model_dump(mode="json")}


# ---------------------------------------------------------------------------
# CREATE endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders",
    operation_id="createWorkOrderV2",
    summary="從已確認 ProblemCard 建立工單 v2（tenant-scoped；idempotent）",
    response_model=WorkOrderEnvelope,
    status_code=201,
    tags=["M06 WorkOrder"],
)
async def create_work_order_v2(
    body: WorkOrderCreateRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    wo, created = await work_order_service.create_from_problem_card(
        tenant_id=tenantId,
        pc_id=body.problem_card_id,
        customer_address=body.customer_address,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        created_by=user.user_id,
    )
    payload = {"data": WorkOrder(**wo).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201 if created else 200, payload)
    return payload


# ---------------------------------------------------------------------------
# State-machine write endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:accept",
    operation_id="acceptWorkOrderV2",
    summary="技師接單 v2（tenant-scoped，assigned → accepted）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def accept_work_order_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.accept_order(
        tenant_id=tenantId, wo_id=id,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:assign",
    operation_id="assignWorkOrderV2",
    summary="手動指派技師 v2（tenant-scoped，created | assigned → assigned）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def assign_work_order_v2(
    body: WorkOrderAssignRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    reason_code = (
        body.reason_code.value if hasattr(body.reason_code, "value") else str(body.reason_code)
    )
    order = await work_order_service.assign_order(
        tenant_id=tenantId,
        wo_id=id,
        technician_id=str(body.technician_id),
        reason_code=reason_code,
        reason_text=body.reason_text,
    )
    # PM Q6=A — 客服繞過自動派工必須留稽核軌跡
    if user.role in _BYPASS_ROLES:
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="manual_dispatch_bypass",
            target_type="work_order",
            target_id=id,
            payload={
                "endpoint": "assignWorkOrderV2",
                "technician_id": str(body.technician_id),
                "reason_code": reason_code,
                "reason_text": body.reason_text or "未提供理由",
            },
        )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:complete",
    operation_id="completeWorkOrderV2",
    summary="完工回報 v2（tenant-scoped，accepted | in_progress → completed）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def complete_work_order_v2(
    body: CompletionReport,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.complete_order(
        tenant_id=tenantId,
        wo_id=id,
        summary=body.summary,
        actual_amount=body.actual_amount,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:confirm",
    operation_id="confirmWorkOrderV2",
    summary="客戶確認結案 v2（tenant-scoped，completed → confirmed）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def confirm_work_order_v2(
    body: WorkOrderConfirmRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.confirm_order(
        tenant_id=tenantId,
        wo_id=id,
        rating=int(body.rating),
        feedback=body.feedback,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:escalate",
    operation_id="escalateWorkOrderV2",
    summary="升級工單 v2（tenant-scoped，不切狀態）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def escalate_work_order_v2(
    body: WorkOrderEscalateRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    level_str = body.level.value if hasattr(body.level, "value") else str(body.level)
    order = await work_order_service.escalate_order(
        tenant_id=tenantId,
        wo_id=id,
        level=level_str,
        reason=body.reason,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# Signature & scope-change
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/signature",
    operation_id="submitWorkOrderSignatureV2",
    summary="雙方電子簽章 v2（tenant-scoped，強制 Idempotency-Key）",
    response_model=ApiResponseGeneric,
    tags=["M06 WorkOrder"],
)
async def submit_work_order_signature_v2(
    body: SignaturePayload,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    result = await signature_service.submit_work_order_signature(
        tenant_id=tenantId,
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
    "/tenants/{tenantId}/work-orders/{id}/scope-change",
    operation_id="recordScopeChangeV2",
    summary="記錄範圍變更申請 v2（tenant-scoped，T5；技師作業中→記錄事件）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def record_scope_change_v2(
    body: _ScopeChangeRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.record_scope_change(
        tenant_id=tenantId,
        wo_id=id,
        reason=body.reason,
        items=[item.model_dump() for item in body.items],
        total_estimate=body.total_estimate,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
