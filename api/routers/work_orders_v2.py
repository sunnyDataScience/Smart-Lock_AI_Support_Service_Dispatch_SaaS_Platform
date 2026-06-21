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

M07 Onsite（CR-0003 P2）：
  - POST /tenants/{tenantId}/work-orders/{woId}/onsite/arrival    → onsiteArrival
  - POST /tenants/{tenantId}/work-orders/{woId}/onsite/completion → onsiteCompletion

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

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
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
from services import (
    audit_log_service,
    evidence_package_service,
    quote_service,
    signature_service,
    work_order_document_service,
    work_order_service,
)

router = APIRouter()

# CR-0027：成本（unit_price）僅後台管理角色可見（server 端 RBAC 遮蔽）
_COST_VISIBLE_ROLES = {"admin", "operations_manager", "tenant_admin"}

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


class WorkOrderFieldsPatchRequest(BaseModel):
    """CR-0043 Tier①：後台設定工單欄位（白名單/enum 驗證由 service 控）。"""

    service_category: str | None = None
    serial_number: str | None = Field(None, max_length=100)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    door_type: str | None = Field(None, max_length=50)
    door_thickness: str | None = Field(None, max_length=50)
    is_interior_door: bool | None = None
    warranty_status: str | None = None
    purchase_date: str | None = None
    install_date: str | None = None
    invoice_no: str | None = Field(None, max_length=100)
    dealer: str | None = Field(None, max_length=150)
    rain_exposure: str | None = None
    special_door_surcharge: bool | None = None
    payment_method: str | None = None
    customer_name: str | None = Field(None, max_length=100)
    customer_phone: str | None = Field(None, max_length=50)
    customer_address: str | None = Field(None, max_length=300)


class WorkOrderReopenRequest(BaseModel):
    """CR-0043 Tier②：返修/reopen — 建子單連回原單（BR-M05-02）。"""

    reason: str = Field(..., min_length=4, max_length=500, description="返修原因（BR-M05-01 必填）")


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
    status: str | None = Query(default=None, description="工單狀態（dispatched/completed/refunded/disputed 等）"),
    brand: str | None = Query(default=None, description="品牌過濾（透過 problem_cards.brand）"),
    created_after: str | None = Query(default=None, description="建立時間下限 ISO 8601（例：最近 7 天）"),
    keyword: str | None = Query(default=None, description="關鍵字搜尋（客戶姓名/地址/電話模糊）"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)

    page = await work_order_service.list_orders(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        problem_card_id=problem_card_id,
        technician_id=technician_id,
        status=status,
        brand=brand,
        created_after=created_after,
        keyword=keyword,
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


@router.patch(
    "/tenants/{tenantId}/work-orders/{id}/fields",
    operation_id="patchWorkOrderFieldsV2",
    summary="後台設定工單欄位 v2（CR-0043；service_category/serial/door/warranty/payment 等）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def patch_work_order_fields_v2(
    body: WorkOrderFieldsPatchRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
) -> dict:
    _cross_tenant_write(user, tenantId)

    fields = body.model_dump(exclude_unset=True)
    order = await work_order_service.update_wo_fields(
        tenant_id=tenantId, wo_id=id, fields=fields,
    )
    return {"data": WorkOrder(**order).model_dump(mode="json")}


@router.get(
    "/tenants/{tenantId}/work-orders/{id}/consents",
    operation_id="getWorkOrderConsentsV2",
    summary="後台唯讀取得工單三段免責同意狀態 v2（CR-0091；複用 consent_service）",
    tags=["M06 WorkOrder"],
)
async def get_work_order_consents_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
) -> dict:
    """派工單模組 4：後台/派工人員唯讀檢視客戶三段免責同意狀態。

    寫入（客戶簽署）走 consumer LIFF `/consumer/consents/{token}`；此端點僅顯示，
    故為唯讀且走後台角色守衛（對齊同檔 fields PATCH 的 _DISPATCH_ALLOWED_ROLES）。
    """
    _cross_tenant_read(user, tenantId)
    from services import consent_service

    return await consent_service.get_consents(work_order_id=id, tenant_id=tenantId)


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:reopen",
    operation_id="reopenWorkOrderV2",
    summary="返修/reopen — 建子單連回原單 v2（CR-0043 / BR-M05-02）",
    response_model=WorkOrderEnvelope,
    status_code=201,
    tags=["M06 WorkOrder"],
)
async def reopen_work_order_v2(
    body: WorkOrderReopenRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)

    child = await work_order_service.reopen_order(
        tenant_id=tenantId, wo_id=id, reason=body.reason, created_by=user.user_id,
    )
    payload = {"data": WorkOrder(**child).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201, payload)
    return payload


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
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
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
    # CR-0039：:complete 為後台 admin/dispatcher 完工 override 路徑（記 summary 為 reason、跳過證據閘）；
    # 技師必須走 /onsite/completion 正規硬閘，否則可繞過照片/簽名/序號驗證。
    if (user.role or "") == "technician":
        raise ApiError(
            "FORBIDDEN",
            "技師請走現場完工送簽端點 /onsite/completion（含照片/簽名硬閘）",
            403,
        )

    order = await work_order_service.complete_order(
        tenant_id=tenantId,
        wo_id=id,
        summary=body.summary,
        actual_amount=body.actual_amount,
        is_override=True,
        override_reason=body.summary,
        actor_role=user.role,
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
# Flow 8 二次派工：admin 強制改派（accepted/in_progress 也可收回，不破壞 wo_id）
# ---------------------------------------------------------------------------


class _ReassignWorkOrderBodyV2(BaseModel):
    """Flow 8 reassign body — 強制改派理由必填以利後續 Q&A 追溯。"""

    technician_id: str = Field(..., description="新指派技師 ID")
    reason: str = Field(..., min_length=1, max_length=500, description="改派原因")


@router.post(
    "/tenants/{tenantId}/work-orders/{id}:reassign",
    operation_id="reassignWorkOrderV2",
    summary="強制改派 v2（Flow 8；assigned | accepted | in_progress 收回 → assigned）",
    response_model=WorkOrderEnvelope,
    tags=["M06 WorkOrder"],
)
async def reassign_work_order_v2(
    body: _ReassignWorkOrderBodyV2,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """Flow 8 二次派工：admin / dispatcher 強制改派工單。

    與 :assign 差異：
      - :assign 只允許 created | assigned → assigned
      - :reassign 允許 assigned | accepted | in_progress → assigned
        （accepted/in_progress 為新增能力，避免 cancel-and-rebuild 破壞性流程）

    錯誤：
      - 409 STATE_CONFLICT 若 wo 已 completed/confirmed/cancelled
      - 422 NO_OP_SAME_TECHNICIAN 若新舊技師相同
      - 404 TECHNICIAN_NOT_FOUND / 409 TECHNICIAN_NOT_AVAILABLE
    """
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.reassign_order(
        tenant_id=tenantId,
        wo_id=id,
        new_technician_id=body.technician_id,
        reason=body.reason,
        actor_user_id=user.user_id,
    )
    # bypass role 留 audit 軌跡（同 assign 路徑）
    if user.role in _BYPASS_ROLES:
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="manual_reassign_bypass",
            target_type="work_order",
            target_id=id,
            payload={
                "endpoint": "reassignWorkOrderV2",
                "new_technician_id": body.technician_id,
                "reason": body.reason,
            },
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
        actor_user_id=user.user_id,
    )
    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# Flow 3 admin override scope_change proposal
# ---------------------------------------------------------------------------


class _ScopeChangeOverrideBody(BaseModel):
    """admin 強制覆寫 scope_change proposal body。"""

    reason: str = Field(..., min_length=1, max_length=500, description="覆寫原因")


@router.post(
    "/tenants/{tenantId}/scope-changes/{proposalId}:admin-override",
    operation_id="adminOverrideScopeChangeV2",
    summary="admin 強制覆寫 scope_change proposal v2（Flow 3；客戶不回應/超時/業務裁決）",
    tags=["M06 WorkOrder"],
)
async def admin_override_scope_change_v2(
    body: _ScopeChangeOverrideBody,
    tenantId: str = Path(...),
    proposalId: str = Path(..., description="scope_changes.id"),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """Flow 3 admin override：客戶不回應 / 超時 / 業務裁決 → admin 強制視同核准。

    錯誤：
      - 404 NOT_FOUND proposal
      - 403 CROSS_TENANT_WRITE proposal 不屬此 tenant
      - 409 CONFLICT proposal 已決議
    """
    _cross_tenant_write(user, tenantId)
    # 延遲 import 避 circular
    from services import scope_change_service

    result = await scope_change_service.admin_override(
        tenant_id=tenantId,
        proposal_id=proposalId,
        approved_by_user_id=user.user_id,
        reason=body.reason,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


# ---------------------------------------------------------------------------
# M07 Onsite — arrival + completion（CR-0003 P2 / spec §M07）
# ---------------------------------------------------------------------------


class _ArrivalGps(BaseModel):
    lat: float = Field(..., description="緯度")
    lng: float = Field(..., description="經度")
    accuracy_m: float | None = Field(default=None, description="GPS 精度（公尺）")


class _ArrivalEventRequest(BaseModel):
    """FR-0006 技師到場事件（GPS + timestamp evidence）。

    對齊 spec ArrivalEvent schema：arrived_at (ISO 8601) + gps。
    到場後以 record_door_check 寫入結構化事件，狀態機推至 in_progress。
    """

    arrived_at: str = Field(..., description="到場時間，ISO 8601 格式")
    gps: _ArrivalGps = Field(..., description="GPS 到場座標")


class _CompletionSubmitRequest(BaseModel):
    """FR-0009 完工送簽（signature evidence + photo evidence）。

    對齊 spec CompletionSubmit schema。
    呼叫 complete_order（accepted | in_progress → completed），
    將 signature + photos 打包為 summary 寫入 service_report。
    """

    signature_evidence_id: str = Field(..., min_length=1, description="簽名媒體 ID")
    photo_evidence_ids: list[str] = Field(..., min_length=1, description="完工照片媒體 ID 清單（至少 1 張）")
    notes: str | None = Field(default=None, max_length=1000, description="備註（選填）")
    teaching_note: str | None = Field(default=None, max_length=1000, description="教學紀錄（BR-M08-03 完工套件，選填）")


@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/onsite/arrival",
    operation_id="onsiteArrival",
    summary="技師到場回報 v2（tenant-scoped，FR-0006 GPS + timestamp；idempotent）",
    status_code=201,
    tags=["M07 Onsite"],
)
async def onsite_arrival_v2(
    body: _ArrivalEventRequest,
    tenantId: str = Path(...),
    woId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """到場事件：寫入 event_type='arrival' 結構化事件（GPS + arrived_at）+ 補 started_at。

    CR-0053：原誤呼 record_door_check（寫 'door_check'）→ submit_door_check_v2 的 arrival 前置閘
    恆 409、started_at 不落致 arrival KPI 失真。改呼 record_arrival 正確寫 'arrival' 事件 + started_at。
    狀態機限制：assigned | accepted | in_progress（_SUBFLOW_FROM）。
    """
    _cross_tenant_write(user, tenantId)

    order = await work_order_service.record_arrival(
        tenant_id=tenantId,
        wo_id=woId,
        arrived_at=body.arrived_at,
        gps=body.gps.model_dump(exclude_none=True),
        actor_user_id=user.user_id,
    )
    payload = {
        "id": order.get("id"),
        "work_order_id": order.get("id"),
        "state": "arrived",
    }
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/onsite/completion",
    operation_id="onsiteCompletion",
    summary="完工送簽 v2（tenant-scoped，FR-0009 signature + photos；idempotent）",
    status_code=201,
    tags=["M07 Onsite"],
)
async def onsite_completion_v2(
    body: _CompletionSubmitRequest,
    tenantId: str = Path(...),
    woId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """完工送簽：呼叫 complete_order（accepted | in_progress → completed）。

    service 呼叫：work_order_service.complete_order
      - summary = "[ONSITE_COMPLETE] sig={signature_evidence_id} photos={...} notes={...}"
      - actual_amount = None（完工金額由後續 AR/Payment 模組確認）
    回傳 CompletionResult（spec）：work_order_id + completed_at。
    """
    _cross_tenant_write(user, tenantId)

    photos_str = ",".join(body.photo_evidence_ids)
    summary_parts = [
        f"[ONSITE_COMPLETE] sig={body.signature_evidence_id}",
        f"photos=[{photos_str}]",
    ]
    if body.notes and body.notes.strip():
        summary_parts.append(f"notes={body.notes.strip()[:500]}")
    summary = " ".join(summary_parts)

    order = await work_order_service.complete_order(
        tenant_id=tenantId,
        wo_id=woId,
        summary=summary,
        actual_amount=None,
        # CR-0039 完工硬閘：技師現場送簽走正規閘（照片≥config / 簽名存在 / 安裝案序號）
        photo_evidence_ids=body.photo_evidence_ids,
        signature_evidence_id=body.signature_evidence_id,
        is_override=False,
        teaching_note=body.teaching_note,  # CR-0050 BR-M08-03 完工套件
    )
    payload = {
        "work_order_id": order.get("id"),
        "completed_at": order.get("completion_time"),
    }
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# CR-0007 door-check v2（強制 arrival 前置 HD-01；checklist freeform jsonb HD-05）
# ─────────────────────────────────────────────────────────────────────────────


class _DoorCheckSubmitRequest(BaseModel):
    """CR-0007 HD-05=(a) freeform jsonb；BE 不驗 checklist 內部結構。"""

    checklist: dict = Field(..., description="freeform jsonb（service 不驗內部結構）")
    photos_before: list[str] = Field(default_factory=list, description="到場前媒體 URL/ID")
    photos_after: list[str] = Field(default_factory=list, description="到場後媒體 URL/ID")
    notes: str | None = Field(default=None, max_length=1000)


@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/door-check",
    operation_id="submitDoorCheckV2",
    summary="門面檢核完整提交 v2（CR-0007 / 強制 arrival 前置 / freeform checklist）",
    status_code=201,
    tags=["M07 Onsite"],
)
async def submit_door_check_v2(
    body: _DoorCheckSubmitRequest,
    tenantId: str = Path(...),
    woId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """CR-0007 HD-01=(a)：缺 arrival event → 409 STATE_CONFLICT。"""
    _cross_tenant_write(user, tenantId)

    result = await work_order_service.submit_door_check_v2(
        tenant_id=tenantId,
        wo_id=woId,
        checklist=body.checklist,
        photos_before=body.photos_before,
        photos_after=body.photos_after,
        notes=body.notes,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ---------------------------------------------------------------------------
# CR-0027 成本拆項（quote line items）+ 客戶版電子工單 PDF
# ---------------------------------------------------------------------------


class _QuoteLineItemRequest(BaseModel):
    """新增公單成本拆項（unit_price 內部成本僅後台；數值預設 mock 待財務覆核）。"""

    item_name: str = Field(..., min_length=1, max_length=120)
    category: str = Field(default="other", description="labor/material/other")
    unit_price: str = Field(..., max_length=20, description="內部成本（僅後台）")
    quantity: int = Field(default=1, ge=1, le=999)
    customer_price: str = Field(..., max_length=20, description="對外金額")
    is_mock: bool = Field(default=True, description="決議 5：mock（打 8 成）待財務覆核")


@router.get(
    "/tenants/{tenantId}/work-orders/{id}/quote-items",
    operation_id="listQuoteItemsV2",
    summary="公單成本拆項列表 v2（unit_price 僅後台角色可見）",
    tags=["M06 WorkOrder"],
)
async def list_quote_items_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)
    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
    return await quote_service.list_line_items(
        tenant_id=tenantId, work_order_id=id, include_cost=include_cost,
    )


@router.post(
    "/tenants/{tenantId}/work-orders/{id}/quote-items",
    operation_id="addQuoteItemV2",
    summary="新增公單成本拆項 v2（後台管理角色；重算對外總額）",
    tags=["M06 WorkOrder"],
)
async def add_quote_item_v2(
    body: _QuoteLineItemRequest,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required("admin", "operations_manager", "tenant_admin")),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)
    result = await quote_service.add_line_item(
        tenant_id=tenantId, work_order_id=id,
        item_name=body.item_name, category=body.category,
        unit_price=body.unit_price, quantity=body.quantity,
        customer_price=body.customer_price, is_mock=body.is_mock,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.get(
    "/tenants/{tenantId}/work-orders/{id}/document",
    operation_id="getWorkOrderDocumentV2",
    summary="客戶版電子工單 PDF v2（只露最終價 + 關防，不含成本明細）",
    tags=["M06 WorkOrder"],
)
async def get_work_order_document_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    _cross_tenant_read(user, tenantId)
    pdf = await work_order_document_service.render_document(
        tenant_id=tenantId, work_order_id=id,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="work-order-{id}.pdf"'},
    )


@router.get(
    "/tenants/{tenantId}/work-orders/{id}/evidence-package",
    operation_id="getWorkOrderEvidencePackageV2",
    summary="工單完工證據包聚合 v2（CR-0055；照片+簽名+到場/門檢事件，唯讀）",
    tags=["M09 Evidence"],
)
async def get_work_order_evidence_package_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant_read(user, tenantId)
    pkg = await evidence_package_service.get_evidence_package(
        tenant_id=tenantId, wo_id=id, role=user.role,
    )
    return {"data": pkg}
