"""Technicians v2 router — tenant-scoped 技師管理端點（CR-0002-α / spec-alignment P2-α / P2-W1）。

對齊 frozen spec §2.2 M05 Technician：
  - GET  /tenants/{tenantId}/technicians          → listTechniciansV2 (cursor 分頁)
  - GET  /tenants/{tenantId}/technicians/{techId} → getTechnicianV2 (單筆詳情)
  - POST  /tenants/{tenantId}/technicians          → createTechnician (onboard FR-0044)
  - PATCH /tenants/{tenantId}/technicians/{techId} → updateTechnicianV2 (CR-0103 admin 編輯基本資料)

舊 flat 路徑 /api/v1/technicians（routers/technicians.py 的 admin 端點）仍保留，
加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

/technicians/me/* 技師自助端點屬 mobile 端範疇，**不遷移**，保留 legacy 路由。
狀態變更（停權/復權/終止）走 technician_lifecycle_v2 的 :suspend/:reactivate/:terminate
（須附 reason，有 audit）；CR-0103 已移除本檔重複且未實作的 :suspend 501 stub。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（POST 寫操作）
  - 呼既有 technician_service 函式，不重寫 SQL
  - envelope：{ data } 對齊既有慣例
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import DISPATCH_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    Technician,
    TechnicianAvailability,
    TechnicianEnvelope,
    TechnicianLevel,
    TechnicianPage,
)
from services import technician_service


class _TechnicianCreateRequest(BaseModel):
    """Inline schema 對齊 spec TechnicianCreate（display_name + coverage_areas）。

    TechnicianCreate 尚未在 generated.py 中生成，故在 router 內 inline 定義。
    DB technicians.phone 為 NOT NULL；spec 未要求 phone → 接受可選，補空字串佔位。
    """

    display_name: str = Field(..., description="技師顯示姓名")
    coverage_areas: list[str] = Field(..., description="服務覆蓋區域代碼清單")
    phone: str | None = Field(default=None, description="聯絡電話（選填）")
    email: str | None = Field(default=None, description="電子郵件（選填）")
    capabilities: list[str] | None = Field(default=None, description="可服務品牌/技能碼")

router = APIRouter()


@router.get(
    "/tenants/{tenantId}/technicians",
    operation_id="listTechniciansV2",
    summary="技師列表 v2（tenant-scoped，admin 視角，cursor 分頁）",
    response_model=TechnicianPage,
    tags=["M05 Technician"],
)
async def list_technicians_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    availability: TechnicianAvailability | None = Query(default=None),
    level: TechnicianLevel | None = Query(default=None),
    status: str | None = Query(default=None, description="技師狀態（pending_approval/active/suspended）"),
    capability: str | None = Query(default=None, description="專長品牌（capabilities jsonb 包含）"),
    service_region: str | None = Query(default=None, description="服務區域"),
    rating_min: float | None = Query(default=None, ge=0.0, le=5.0, description="最低評分"),
    keyword: str | None = Query(default=None, description="關鍵字搜尋（name/phone/email 模糊）"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await technician_service.list_technicians(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        availability=availability.value if availability else None,
        level=level.value if level else None,
        status=status,
        capability=capability,
        service_region=service_region,
        rating_min=rating_min,
        keyword=keyword,
    )
    return {
        "items": [Technician(**t).model_dump(mode="json") for t in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/tenants/{tenantId}/technicians/{techId}",
    operation_id="getTechnicianV2",
    summary="技師單筆詳情 v2（tenant-scoped，admin 視角）",
    response_model=TechnicianEnvelope,
    tags=["M05 Technician"],
)
async def get_technician_v2(
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    technician = await technician_service.get_technician(
        tenant_id=tenantId, technician_id=techId
    )
    return {"data": Technician(**technician).model_dump(mode="json")}


@router.get(
    "/tenants/{tenantId}/technicians/{techId}/schedule",
    operation_id="getTechnicianScheduleV2",
    summary="技師月排班 v2（admin 視角：每日工單數 + 休假/備勤；詳情頁本週排班用）",
    tags=["M05 Technician"],
)
async def get_technician_schedule_v2(
    tenantId: str = Path(...),
    techId: str = Path(...),
    month: str = Query(..., description="YYYY-MM"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """CIA-additive（2026-07-02 師傅測試修復）：後台技師詳情頁「本週排班」原為
    hardcoded mock（固定 2026/04/20-26 早晚班），本端點供其接真資料。
    讀取 me/schedule 同源資料（工單數 keyed by technician_id；休假/備勤走
    technician_schedule_requests），唯讀、不含 pending_requests。"""
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    from services import technician_schedule_service

    return await technician_schedule_service.get_schedule_for_technician(
        tenant_id=tenantId, tech_id=techId, month_str=month
    )


@router.post(
    "/tenants/{tenantId}/technicians",
    operation_id="createTechnician",
    summary="Onboard 新技師 v2（tenant-scoped, FR-0044 / spec-alignment P2-W1）",
    response_model=TechnicianEnvelope,
    status_code=201,
    tags=["M05 Technician"],
)
async def create_technician_v2(
    body: _TechnicianCreateRequest,
    response: Response,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    technician, created = await technician_service.create_technician(
        tenant_id=tenantId,
        display_name=body.display_name,
        coverage_areas=body.coverage_areas,
        phone=body.phone,
        email=body.email,
        capabilities=body.capabilities,
    )

    response.status_code = 201 if created else 200
    payload: dict = {"data": Technician(**technician).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload


class _TechnicianUpdateRequest(BaseModel):
    """CR-0103 admin 編輯技師基本資料（部分更新，欄位皆選填；只更新有帶的欄位）。
    狀態變更不走這裡 —— active↔suspended 用 lifecycle :suspend/:reactivate（須附 reason）。
    CR-0104：+level（等級手動指派，值域 S/A/B/C 由 TechnicianLevel enum 守門）。"""

    display_name: str | None = Field(default=None, description="技師顯示姓名")
    phone: str | None = Field(default=None, description="聯絡電話")
    email: str | None = Field(default=None, description="電子郵件")
    coverage_areas: list[str] | None = Field(default=None, description="服務覆蓋區域代碼清單")
    capabilities: list[str] | None = Field(default=None, description="可服務品牌/技能碼")
    level: TechnicianLevel | None = Field(default=None, description="技師等級（S/A/B/C，手動指派）")


@router.patch(
    "/tenants/{tenantId}/technicians/{techId}",
    operation_id="updateTechnicianV2",
    summary="編輯技師基本資料 v2（tenant-scoped；狀態變更走 lifecycle :suspend/:reactivate）",
    response_model=TechnicianEnvelope,
    tags=["M05 Technician"],
)
async def update_technician_v2(
    body: _TechnicianUpdateRequest,
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # 請求欄位 → service patch key（display_name→name、coverage_areas→regions），
    # None 欄位不更新（部分更新語意）。
    patch = {
        "name": body.display_name,
        "phone": body.phone,
        "email": body.email,
        "capabilities": body.capabilities,
        "regions": body.coverage_areas,
        "level": body.level.value if body.level else None,
    }
    technician = await technician_service.update_technician(
        tenant_id=tenantId, technician_id=techId, patch=patch,
    )
    return {"data": Technician(**technician).model_dump(mode="json")}
