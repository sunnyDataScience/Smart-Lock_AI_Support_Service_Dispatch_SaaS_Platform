"""Platform console 品牌申請 router(CR-0114 R2)。

- POST /platform/brand-applications      公開(landing 品牌 CTA;per-IP DB 限流)
- GET  /platform/brand-applications      平台管理員(?status= 過濾)
- POST /platform/brand-applications/{id}:approve   核准 + 回開站指引文字
- POST /platform/brand-applications/{id}:reject    拒絕(reason 必填)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field

from core.deps import CurrentUser, require_platform_admin
from services import brand_application_service

logger = logging.getLogger("api.routers.platform_brand_applications")
router = APIRouter()


class BrandApplicationBody(BaseModel):
    # 欄位對齊原 VendorRegisterBody(auth.py)但**不收 password**:
    # 申請是意向書,核准後人工開站+聯絡,不建任何帳號(CR-0114 §4.2)。
    application_type: str = Field(pattern="^(brand|locksmith|distributor)$")
    company_name: str = Field(min_length=1, max_length=150)
    contact_name: str = Field(min_length=1, max_length=150)
    tax_id: str = Field(pattern=r"^\d{8}$", description="公司統編 8 碼")
    phone: str = Field(pattern=r"^09\d{8}$")
    email: EmailStr
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class ApproveBody(BaseModel):
    slug: str | None = Field(default=None, max_length=30, description="品牌代號(未填自動產生)")
    review_notes: str | None = Field(default=None, max_length=1000)


class RejectBody(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post(
    "/platform/brand-applications",
    operation_id="submitBrandApplication",
    summary="品牌申請(公開,landing 表單)",
    status_code=201,
)
async def submit_brand_application(body: BrandApplicationBody, request: Request) -> dict:
    client_ip = request.client.host if request.client else None
    return await brand_application_service.submit(
        application_type=body.application_type,
        company_name=body.company_name,
        contact_name=body.contact_name,
        tax_id=body.tax_id,
        phone=body.phone,
        email=body.email,
        address=body.address,
        notes=body.notes,
        request_ip=client_ip,
    )


@router.get(
    "/platform/brand-applications",
    operation_id="listBrandApplications",
    summary="品牌申請列表",
    status_code=200,
)
async def list_brand_applications(
    status: str | None = None,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await brand_application_service.list_applications(status)


@router.post(
    "/platform/brand-applications/{applicationId}:approve",
    operation_id="approveBrandApplication",
    summary="核准品牌申請(回開站指引)",
    status_code=200,
)
async def approve_brand_application(
    applicationId: str,
    body: ApproveBody | None = None,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await brand_application_service.approve(
        app_id=applicationId,
        reviewer_id=user.user_id,
        slug=(body.slug if body else None),
        review_notes=(body.review_notes if body else None),
    )


@router.post(
    "/platform/brand-applications/{applicationId}:reject",
    operation_id="rejectBrandApplication",
    summary="拒絕品牌申請",
    status_code=200,
)
async def reject_brand_application(
    applicationId: str,
    body: RejectBody,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await brand_application_service.reject(
        app_id=applicationId,
        reviewer_id=user.user_id,
        reason=body.reason,
    )
