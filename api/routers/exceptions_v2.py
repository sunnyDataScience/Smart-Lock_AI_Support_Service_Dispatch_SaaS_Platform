"""M15 Exceptions inbox / approve v2 — tenant-scoped（CR-0003 P2）。

spec 對齊：
  GET  /tenants/{tenantId}/exceptions:inbox
       → listExceptionsInbox（整併 legacy GET /api/v1/admin/schedule-requests）
  POST /tenants/{tenantId}/exceptions/{exceptionId}:approve
       → approveException（body 帶 decision approve/reject，整併兩條 legacy POST）

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（POST 寫操作）
  - 呼既有 technician_schedule_service 函式，零重寫業務邏輯
  - ExceptionDecision body 的 decision 欄位決定 approve vs reject
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import technician_schedule_service

router = APIRouter()

_admin_only = role_required("admin", "operations_manager")


class ExceptionDecision(BaseModel):
    """POST :approve body — decision 欄位區分 approve 與 reject。"""

    decision: Literal["approve", "reject"] = Field(
        ...,
        description="'approve' 核准；'reject' 拒絕",
    )
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/exceptions:inbox
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/exceptions:inbox",
    operation_id="listExceptionsInbox",
    summary="列出 tenant 內例外申請 inbox（tenant-scoped，整併 schedule-requests）",
    tags=["M15 Exception"],
)
async def list_exceptions_inbox(
    tenantId: str = Path(...),
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(
        default=None
    ),
    type: Literal["leave", "standby"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(_admin_only),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await technician_schedule_service.list_schedule_requests(
        tenant_id=tenantId,
        status=status,
        type_filter=type,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/exceptions/{exceptionId}:approve
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/exceptions/{exceptionId}:approve",
    operation_id="approveException",
    summary="核准或拒絕例外申請（tenant-scoped，decision 欄位區分 approve/reject）",
    tags=["M15 Exception"],
)
async def approve_exception(
    body: ExceptionDecision,
    tenantId: str = Path(...),
    exceptionId: str = Path(...),
    user: CurrentUser = Depends(_admin_only),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # 將 ExceptionDecision.decision（approve/reject）對應到 service 接受的
    # Literal["approved", "rejected"]（tech schedule service 既有格式）
    service_decision: Literal["approved", "rejected"] = (
        "approved" if body.decision == "approve" else "rejected"
    )

    result = await technician_schedule_service.resolve_schedule_request(
        tenant_id=tenantId,
        resolver_user_id=user.user_id,
        request_id=exceptionId,
        decision=service_decision,
        note=body.note,
    )

    if idem is not None:
        await idem.save(200, result)

    return result
