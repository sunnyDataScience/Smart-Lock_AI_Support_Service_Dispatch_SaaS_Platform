"""Platform console 廠商管理 router。

UAT R2 W3-2 業主裁決（2026-07-18）：廠商自助註冊全鏈退場（公開
POST /vendors/register 已移除，20260702 前端退場決議貫徹到後端）；
廠商帳號一律由平台方**代建**，建立即 active（不再有 pending_approval
待審流，:approve / :reject 端點一併移除）。

全部 gate = require_platform_admin（非 tenant-scoped，跨品牌視角）。

- GET  /platform/vendors?status=
- POST /platform/vendors          代建廠商帳號（直接啟用）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, require_platform_admin
from services import platform_vendor_service as svc

logger = logging.getLogger("api.routers.platform_vendors")
router = APIRouter()


class VendorCreateBody(BaseModel):
    """平台代建廠商帳號（釘定契約：name/company_name/tax_id/phone/email/password）。

    vendor_type 與 address 選填（additive；未帶 vendor_type 預設 brand）。
    """

    name: str = Field(min_length=1, max_length=150)
    company_name: str = Field(min_length=1, max_length=150)
    tax_id: str = Field(pattern=r"^\d{8}$", description="統一編號 8 碼")
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72 byte 上限
    vendor_type: str = Field(default="brand", description="brand/locksmith/distributor")
    address: str | None = Field(default=None, max_length=300)


@router.get(
    "/platform/vendors",
    operation_id="listPlatformVendors",
    summary="跨品牌廠商清單（平台管理用）",
    status_code=200,
)
async def list_vendors(
    status: str | None = Query(default=None),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_vendors(status=status)


@router.post(
    "/platform/vendors",
    operation_id="platformCreateVendor",
    summary="平台代建廠商帳號（建立即啟用，取代自助註冊）",
    status_code=201,
)
async def create_vendor(
    body: VendorCreateBody,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.create_vendor(
        req=body.model_dump(), actor_user_id=user.user_id
    )
