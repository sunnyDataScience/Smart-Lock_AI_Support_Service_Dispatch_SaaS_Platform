"""Vendors v2 router — 廠商（發案者）管理（CR-0029 收尾）。

  - GET  /tenants/{tenantId}/vendors?status=pending_approval  → listVendorsV2
  - POST /tenants/{tenantId}/vendors/{id}:approve             → approveVendorV2
  - POST /tenants/{tenantId}/vendors/{id}:reject              → rejectVendorV2

註冊建 vendors(pending_approval)；本 router 給管理員核准/拒絕，收完註冊閉環。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import vendor_service

router = APIRouter()

_VENDOR_ADMIN_ROLES = ("admin", "operations_manager", "tenant_admin")


def _cross_tenant(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)


class _RejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


@router.get(
    "/tenants/{tenantId}/vendors",
    operation_id="listVendorsV2",
    summary="廠商列表 v2（可依 status 過濾，如 pending_approval）",
    tags=["M14 Vendor"],
)
async def list_vendors_v2(
    tenantId: str = Path(...),
    status: str | None = Query(default=None, description="pending_approval/active/suspended/rejected"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant(user, tenantId)
    return await vendor_service.list_vendors(tenant_id=tenantId, status=status)


@router.post(
    "/tenants/{tenantId}/vendors/{id}:approve",
    operation_id="approveVendorV2",
    summary="核准廠商 v2（pending_approval → active；管理角色）",
    tags=["M14 Vendor"],
)
async def approve_vendor_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_VENDOR_ADMIN_ROLES)),
) -> dict:
    _cross_tenant(user, tenantId)
    return {"data": await vendor_service.approve_vendor(
        tenant_id=tenantId, vendor_id=id, approver_id=user.user_id)}


@router.post(
    "/tenants/{tenantId}/vendors/{id}:reject",
    operation_id="rejectVendorV2",
    summary="拒絕廠商 v2（pending_approval → rejected；管理角色）",
    tags=["M14 Vendor"],
)
async def reject_vendor_v2(
    body: _RejectBody,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_VENDOR_ADMIN_ROLES)),
) -> dict:
    _cross_tenant(user, tenantId)
    return {"data": await vendor_service.reject_vendor(
        tenant_id=tenantId, vendor_id=id, approver_id=user.user_id, reason=body.reason)}
