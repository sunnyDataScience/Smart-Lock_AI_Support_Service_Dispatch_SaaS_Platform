"""Approval Inbox v2 router — FR-0049 MVP 起手。

1 endpoint:
  GET /tenants/{tenantId}/approval-inbox?type=...&limit=100
    → 統一聚合所有 pending approval task (scope_change / refund /
       dispute / reschedule / recon_exception)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import approval_inbox_service as svc

logger = logging.getLogger("api.approval_inbox_v2")

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/approval-inbox",
    operation_id="listApprovalInbox",
    summary="統一 approval inbox（聚合 5 種 pending approval task）— FR-0049 MVP",
    response_model=dict,
)
async def list_approval_inbox(
    tenantId: str = Path(...),
    type: str | None = Query(
        default=None,
        description="scope_change|refund|dispute|reschedule|recon_exception|all",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await svc.list_pending_approvals(
        tenant_id=tenantId, type_filter=type, limit=limit,
    )
