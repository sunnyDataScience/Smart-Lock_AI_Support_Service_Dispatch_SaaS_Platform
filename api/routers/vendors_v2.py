"""Vendors v2 router — 廠商（發案者）唯讀 + 自助（CR-0029 → CR-0114 收尾）。

  - GET /vendors/me                                → getVendorSelfV2（廠商自身 profile）
  - GET /tenants/{tenantId}/vendors?status=...     → listVendorsV2（品牌唯讀）

**廠商帳號由平台代建**（UAT R2 W3-2 裁決 2026-07-18：自助註冊與核准/拒絕
流整條退場，routers/platform_vendors.py 的 POST /platform/vendors 建立即
active）。品牌端只保留唯讀清單與廠商自身 profile。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import vendor_service

router = APIRouter()


def _cross_tenant(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)


@router.get(
    "/vendors/me",
    operation_id="getVendorSelfV2",
    summary="廠商自身 profile（CR-0029 廠商專區；以登入 user_id 取）",
    tags=["M14 Vendor"],
)
async def get_vendor_self_v2(
    user: CurrentUser = Depends(role_required("vendor")),
) -> dict:
    vendor = await vendor_service.get_vendor_by_user_id(user_id=user.user_id)
    if not vendor:
        raise ApiError("NOT_FOUND", "Vendor profile not found for current user", 404)
    return {"data": vendor}


@router.get(
    "/tenants/{tenantId}/vendors",
    operation_id="listVendorsV2",
    summary="廠商列表 v2（品牌唯讀；廠商帳號由平台代建）",
    tags=["M14 Vendor"],
)
async def list_vendors_v2(
    tenantId: str = Path(...),
    status: str | None = Query(default=None, description="pending_approval/active/suspended/rejected"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _cross_tenant(user, tenantId)
    return await vendor_service.list_vendors(tenant_id=tenantId, status=status)
