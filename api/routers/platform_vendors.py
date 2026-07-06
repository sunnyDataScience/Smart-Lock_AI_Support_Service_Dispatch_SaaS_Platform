"""Platform console 廠商審核 router。

廠商（發案方登入帳號 role='vendor'）的註冊審核自品牌後台移到平台方統一管。
全部 gate = require_platform_admin（非 tenant-scoped，跨品牌視角）；
approver 取已驗簽 token sub。

- GET  /platform/vendors?status=
- POST /platform/vendors/{id}:approve
- POST /platform/vendors/{id}:reject
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_platform_admin
from services import platform_vendor_service as svc

logger = logging.getLogger("api.routers.platform_vendors")
router = APIRouter()


class RejectBody(BaseModel):
    reason: str | None = None


@router.get(
    "/platform/vendors",
    operation_id="listPlatformVendors",
    summary="跨品牌廠商清單（平台審核用）",
    status_code=200,
)
async def list_vendors(
    status: str | None = Query(default=None),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_vendors(status=status)


@router.post(
    "/platform/vendors/{vendorId}:approve",
    operation_id="platformApproveVendor",
    summary="核准廠商（pending_approval → active）",
    status_code=200,
)
async def approve_vendor(
    vendorId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {"data": await svc.approve_vendor(vendor_id=vendorId, approver_id=user.user_id)}


@router.post(
    "/platform/vendors/{vendorId}:reject",
    operation_id="platformRejectVendor",
    summary="拒絕廠商（pending_approval → rejected）",
    status_code=200,
)
async def reject_vendor(
    body: RejectBody,
    vendorId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {
        "data": await svc.reject_vendor(
            vendor_id=vendorId, approver_id=user.user_id, reason=body.reason,
        )
    }
