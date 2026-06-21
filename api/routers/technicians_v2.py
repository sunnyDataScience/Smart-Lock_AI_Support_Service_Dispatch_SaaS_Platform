"""Technicians v2 router — tenant-scoped 技師管理端點（CR-0002-α / spec-alignment P2-α / P2-W1）。

對齊 frozen spec §2.2 M05 Technician：
  - GET  /tenants/{tenantId}/technicians          → listTechniciansV2 (cursor 分頁)
  - GET  /tenants/{tenantId}/technicians/{techId} → getTechnicianV2 (單筆詳情)
  - POST /tenants/{tenantId}/technicians          → createTechnician (onboard FR-0044)
  - POST /tenants/{tenantId}/technicians/{techId}:suspend → suspendTechnicianV2

舊 flat 路徑 /api/v1/technicians（routers/technicians.py 的 admin 端點）仍保留，
加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

/technicians/me/* 技師自助端點屬 mobile 端範疇，**不遷移**，保留 legacy 路由。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（POST 寫操作）
  - 呼既有 technician_service 函式，不重寫 SQL
  - envelope：{ data } 對齊既有慣例
  - suspend：legacy service 尚無對應實作 → 標 TODO stub（回 501）
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.responses import JSONResponse

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


@router.post(
    "/tenants/{tenantId}/technicians/{techId}:suspend",
    operation_id="suspendTechnicianV2",
    summary="暫停技師派工 v2（tenant-scoped）— TODO: 待 service 層實作",
    tags=["M05 Technician"],
    status_code=501,
)
async def suspend_technician_v2(
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> JSONResponse:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # TODO（M05 suspend）: technician_service 尚無 suspend 實作。
    # 待 service 層新增 suspend_technician(tenant_id, technician_id) 後接入。
    return JSONResponse(
        status_code=501,
        content={
            "error_code": "NOT_IMPLEMENTED",
            "message": "suspend endpoint is not yet implemented",
        },
    )
