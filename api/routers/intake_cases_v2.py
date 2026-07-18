"""Intake Case v2 router — M01 進線 Case 入口（CR-0108，tenant-scoped）。

客服多渠道代建 Case（D1：line/phone/web/referral），建案啟動 first-response SLA。
  - GET    /tenants/{tenantId}/cases            → 列表（篩 status / source_channel）
  - POST   /tenants/{tenantId}/cases            → 客服代建案
  - GET    /tenants/{tenantId}/cases/{caseId}   → 詳情（含 sla_overdue）
  - PATCH  /tenants/{tenantId}/cases/{caseId}   → 更新狀態/補資訊（in_progress 記首次回應）

對齊 v2 慣例：require_tenant + cross-tenant guard（ADR-0030）、寫操作 BACKOFFICE_ROLES
（含 customer_service —— 客服代建案）、POST idempotency、envelope { data }。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import intake_case_service

router = APIRouter()


class _CaseCreateRequest(BaseModel):
    source_channel: str = Field(..., description="進線渠道：line/phone/web/referral")
    summary: str | None = Field(default=None, description="需求摘要")
    customer_name: str | None = Field(default=None)
    customer_phone: str | None = Field(default=None)
    customer_line_id: str | None = Field(default=None)
    customer_id: str | None = Field(default=None, description="既有客戶 users.id（比對到則填）")
    # UAT-0718 W5-4：關聯欄（選填；LINE 自動建案由後端回填，手動建案可不填）
    conversation_id: str | None = Field(default=None, description="來源對話 id（可空）")
    problem_card_id: str | None = Field(default=None, description="關聯問題卡 id（可空）")
    work_order_id: str | None = Field(default=None, description="關聯工單 id（可空）")


class _CaseUpdateRequest(BaseModel):
    status: str | None = Field(default=None, description="open/in_progress/closed")
    summary: str | None = Field(default=None)
    customer_name: str | None = Field(default=None)
    customer_phone: str | None = Field(default=None)


def _guard_tenant(user: CurrentUser, tenant_id: str, write: bool) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


@router.get(
    "/tenants/{tenantId}/cases",
    operation_id="listIntakeCases",
    summary="進線 Case 列表（tenant-scoped）",
    tags=["M01 Intake"],
)
async def list_cases(
    tenantId: str = Path(...),
    status: str | None = Query(default=None),
    source_channel: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId, write=False)
    result = await intake_case_service.list_cases(
        tenant_id=tenantId, status=status, source_channel=source_channel, limit=limit
    )
    return {"data": result["items"]}


@router.post(
    "/tenants/{tenantId}/cases",
    operation_id="createIntakeCase",
    summary="客服代建進線 Case（多渠道）",
    status_code=201,
    tags=["M01 Intake"],
)
async def create_case(
    body: _CaseCreateRequest,
    response: Response,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    case = await intake_case_service.create_case(
        tenant_id=tenantId,
        source_channel=body.source_channel,
        summary=body.summary,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        customer_line_id=body.customer_line_id,
        customer_id=body.customer_id,
        created_by=user.user_id,
        conversation_id=body.conversation_id,
        problem_card_id=body.problem_card_id,
        work_order_id=body.work_order_id,
    )
    response.status_code = 201
    payload = case  # service 回 {"data": ...}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.get(
    "/tenants/{tenantId}/cases/{caseId}",
    operation_id="getIntakeCase",
    summary="進線 Case 詳情",
    tags=["M01 Intake"],
)
async def get_case(
    tenantId: str = Path(...),
    caseId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId, write=False)
    return await intake_case_service.get_case(tenant_id=tenantId, case_id=caseId)


@router.patch(
    "/tenants/{tenantId}/cases/{caseId}",
    operation_id="updateIntakeCase",
    summary="更新進線 Case（狀態/補資訊；in_progress 記首次回應）",
    tags=["M01 Intake"],
)
async def update_case(
    body: _CaseUpdateRequest,
    tenantId: str = Path(...),
    caseId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    return await intake_case_service.update_case(
        tenant_id=tenantId, case_id=caseId, patch=body.model_dump(exclude_unset=True)
    )
