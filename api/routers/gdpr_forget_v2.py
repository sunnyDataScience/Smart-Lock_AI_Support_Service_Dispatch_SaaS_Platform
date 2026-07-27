"""GDPR Forget v2 router — FR-0053 Phase II MVP 6 endpoints。

1. POST   /tenants/{tid}/gdpr/forget-requests           建 request
2. GET    /tenants/{tid}/gdpr/forget-requests           列 requests (status filter)
3. GET    /tenants/{tid}/gdpr/forget-requests/{id}      取單筆
4. POST   .../{id}:legal-hold-deny                       admin 標 legal hold
5. POST   .../{id}:soft-delete                          T0+ 軟刪 + clear PII
6. POST   .../{id}:hard-delete                          T+30 硬刪 (cooldown 後)
7. POST   .../{id}:cancel                               客戶撤回
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel

from core.deps import FULL_ACCESS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import gdpr_forget_service as svc

logger = logging.getLogger("api.gdpr_forget_v2")

router = APIRouter()


async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


class CreateRequestBody(BaseModel):
    subject_user_id: str
    requested_by: str = "customer_self"
    notes: str | None = None


class LegalHoldDenyBody(BaseModel):
    legal_hold_reason: str
    expected_release_at: datetime | None = None


@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests",
    operation_id="createGdprForgetRequest",
    summary="建 GDPR forget request (T0 received)",
    response_model=dict,
    status_code=201,
)
async def create_request(
    body: CreateRequestBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.create_forget_request(
        tenant_id=tenantId,
        subject_user_id=body.subject_user_id,
        requested_by=body.requested_by,
        actor_user_id=initiator,
        notes=body.notes,
    )
    return {"data": result}


@router.get(
    "/tenants/{tenantId}/gdpr/forget-requests",
    operation_id="listGdprForgetRequests",
    summary="列 GDPR forget requests（可選 status filter）",
    response_model=dict,
)
async def list_requests(
    tenantId: str = Path(...),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_forget_requests(
        tenant_id=tenantId, status=status, limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}",
    operation_id="getGdprForgetRequest",
    summary="取單筆 forget request",
    response_model=dict,
)
async def get_request(
    tenantId: str = Path(...),
    requestId: str = Path(...),
    # CR-0183 補漏（2026-07-27）：同資源的 list 端點已上守衛、本明細端點卻只有
    # require_tenant → 低權限角色只要知道/猜到 ID 就能直接讀明細，繞過 list 守衛。
    # 守衛不得弱於同資源的 list。
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return {"data": await svc._get_request(requestId)}


@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}:legal-hold-deny",
    operation_id="denyGdprForgetForLegalHold",
    summary="標 legal-hold 拒絕（received → legal_hold_denied）",
    response_model=dict,
)
async def legal_hold_deny(
    body: LegalHoldDenyBody,
    tenantId: str = Path(...),
    requestId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.deny_legal_hold(
        request_id=requestId,
        legal_hold_reason=body.legal_hold_reason,
        expected_release_at=body.expected_release_at,
        actor_user_id=initiator,
    )
    return {"data": result}


@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}:soft-delete",
    operation_id="softDeleteGdprForgetRequest",
    summary="T0+ 軟刪 + clear PII（received → soft_deleted）",
    response_model=dict,
)
async def soft_delete(
    tenantId: str = Path(...),
    requestId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.soft_delete(request_id=requestId, actor_user_id=initiator)
    return {"data": result}


@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}:hard-delete",
    operation_id="hardDeleteGdprForgetRequest",
    summary="T+30 硬刪（soft_deleted → hard_deleted；cooldown 後）",
    response_model=dict,
)
async def hard_delete(
    tenantId: str = Path(...),
    requestId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.hard_delete(request_id=requestId, actor_user_id=initiator)
    return {"data": result}


@router.post(
    "/tenants/{tenantId}/gdpr/forget-requests/{requestId}:cancel",
    operation_id="cancelGdprForgetRequest",
    summary="客戶撤回 forget request（received → cancelled）",
    response_model=dict,
)
async def cancel_request(
    tenantId: str = Path(...),
    requestId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    initiator: str = Depends(_require_initiator),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.cancel_request(request_id=requestId, actor_user_id=initiator)
    return {"data": result}
