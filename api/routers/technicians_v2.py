"""Technicians v2 router — tenant-scoped 技師「唯讀」端點（CR-0002-α → CR-0114 收斂）。

對齊 CR-0114 裁決 1「師傅審核歸平台方;品牌端唯讀」—— 本檔只留讀端點：
  - GET  /tenants/{tenantId}/technicians               → listTechniciansV2 (cursor 分頁)
  - GET  /tenants/{tenantId}/technicians/{techId}      → getTechnicianV2 (單筆詳情)
  - GET  /tenants/{tenantId}/technicians/{techId}/schedule → getTechnicianScheduleV2

**寫端點已於 CR-0114 收斂輪移除**（師傅身分屬平台方職權，品牌端不可寫）：
  - POST createTechnician（FR-0044 品牌端 onboard）→ 廢止;師傅入口=3001 /tech-register
    自助註冊 + platform console 審核（routers/platform_technicians.py）。
  - PATCH updateTechnicianV2（CR-0103 編輯基本資料 + CR-0104 level）→ 廢止;
    師傅主檔（姓名/技能/區域/等級）異動歸平台方（platform console 編輯功能為後續輪）。

/technicians/me/* 技師自助端點屬 mobile 端範疇，保留 legacy 路由（routers/technicians.py）。
狀態變更（核准/停權/復權/終止）走 platform console（platform_technicians.py）。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 technician_service 函式，不重寫 SQL
  - envelope：{ data } 對齊既有慣例
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import (
    Technician,
    TechnicianAvailability,
    TechnicianEnvelope,
    TechnicianLevel,
    TechnicianPage,
)
from services import technician_service

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
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
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
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES, "reviewer")),
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
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
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

