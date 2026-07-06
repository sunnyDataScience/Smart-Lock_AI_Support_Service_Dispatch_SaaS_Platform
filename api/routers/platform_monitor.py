"""Platform console 維運監控 router(CR-0116)。

監控目標 registry CRUD + 跨品牌 /health 並發探測。全部 gate =
require_platform_admin(非 tenant-scoped,跨品牌視角)。

- GET    /platform/monitor-targets          → registry 清單
- GET    /platform/monitor-targets/health   → 並發探測所有啟用目標(即時,不落庫)
- POST   /platform/monitor-targets          → 新增目標
- PATCH  /platform/monitor-targets/{id}     → 更新目標
- DELETE /platform/monitor-targets/{id}     → 刪除目標

⚠️ 路由排序:字面段 `health` 必須宣告在 `{id}` catch-all 之前,否則
`GET /monitor-targets/health` 會被 `{targetId}` 吃掉(比照 lifecycle-events 慣例)。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from core.deps import CurrentUser, require_platform_admin
from services import platform_monitor_service as svc

logger = logging.getLogger("api.routers.platform_monitor")
router = APIRouter()


class TargetCreateBody(BaseModel):
    brand: str
    label: str
    url: str
    enabled: bool = True
    sort_order: int = 0
    note: str | None = None


class TargetUpdateBody(BaseModel):
    brand: str | None = None
    label: str | None = None
    url: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    note: str | None = None


@router.get(
    "/platform/monitor-targets",
    operation_id="listMonitorTargets",
    summary="維運監控目標 registry 清單",
    status_code=200,
)
async def list_targets(
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_targets()


# 字面段 health 必須在 {targetId} 之前宣告
@router.get(
    "/platform/monitor-targets/health",
    operation_id="probeMonitorTargets",
    summary="並發探測所有啟用目標 /health(即時,不落庫)",
    status_code=200,
)
async def probe_health(
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.probe_health()


@router.post(
    "/platform/monitor-targets",
    operation_id="createMonitorTarget",
    summary="新增監控目標",
    status_code=201,
)
async def create_target(
    body: TargetCreateBody,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.create_target(
        brand=body.brand, label=body.label, url=body.url,
        enabled=body.enabled, sort_order=body.sort_order, note=body.note,
    )


@router.patch(
    "/platform/monitor-targets/{targetId}",
    operation_id="updateMonitorTarget",
    summary="更新監控目標",
    status_code=200,
)
async def update_target(
    body: TargetUpdateBody,
    targetId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    patch = body.model_dump(exclude_unset=True)
    return await svc.update_target(target_id=targetId, patch=patch)


@router.delete(
    "/platform/monitor-targets/{targetId}",
    operation_id="deleteMonitorTarget",
    summary="刪除監控目標",
    status_code=200,
)
async def delete_target(
    targetId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    await svc.delete_target(target_id=targetId)
    return {"data": {"id": targetId}, "message": "已刪除"}
