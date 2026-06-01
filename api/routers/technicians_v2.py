"""Technicians v2 router — tenant-scoped 技師管理端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M05 Technician：
  - GET  /tenants/{tenantId}/technicians          → listTechniciansV2 (cursor 分頁)
  - GET  /tenants/{tenantId}/technicians/{techId} → getTechnicianV2 (單筆詳情)
  - POST /tenants/{tenantId}/technicians/{techId}:suspend → suspendTechnicianV2

舊 flat 路徑 /api/v1/technicians（routers/technicians.py 的 admin 端點）仍保留，
加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。

/technicians/me/* 技師自助端點屬 mobile 端範疇，**不遷移**，保留 legacy 路由。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 technician_service 函式，不重寫 SQL
  - envelope：{ data } 對齊既有慣例
  - suspend：legacy service 尚無對應實作 → 標 TODO stub（回 501）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant
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
    "/tenants/{tenantId}/technicians/{techId}:suspend",
    operation_id="suspendTechnicianV2",
    summary="暫停技師派工 v2（tenant-scoped）— TODO: 待 service 層實作",
    tags=["M05 Technician"],
    status_code=501,
)
async def suspend_technician_v2(
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
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
