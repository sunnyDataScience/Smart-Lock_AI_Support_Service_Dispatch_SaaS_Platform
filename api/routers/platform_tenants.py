"""Platform console 租戶管理 router(CR-0118)。

已開站租戶 registry 檢視 + 生命週期(平台層標示)。全部 gate =
require_platform_admin(非 tenant-scoped,跨品牌視角)。

- GET  /platform/tenants            → registry 清單(?status= 過濾)
- GET  /platform/tenants/{id}       → 租戶詳情
- POST /platform/tenants/{id}:suspend    → 停用(平台層標示;active → suspended)
- POST /platform/tenants/{id}:reactivate → 恢復(suspended → active)

註:租戶由「核准品牌申請」自動登錄(brand_application_service.approve 連動),
故此 router **無 create 端點**。停用僅平台層標示;實際停站走維運(CR-0113 方案 A)。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_platform_admin
from services import platform_tenant_service as svc

logger = logging.getLogger("api.routers.platform_tenants")
router = APIRouter()


class LicenseUpdateBody(BaseModel):
    """CR-0166 R3：租戶 License 更新（平台管理員）。全欄選填，未帶＝不變。"""
    plan_tier: str | None = Field(default=None, description="free/standard/pro/enterprise")
    entitled_modules: list[str] | None = Field(
        default=None, description="開通模組（core 自動保留）：refinery/studio/compiler")
    license_expires_at: str | None = Field(default=None, description="到期 ISO 時間（null=無期限）")


@router.get(
    "/platform/tenants",
    operation_id="listPlatformTenants",
    summary="已開站租戶 registry 清單",
    status_code=200,
)
async def list_tenants(
    status: str | None = None,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_tenants(status)


@router.get(
    "/platform/tenants/{tenantId}",
    operation_id="getPlatformTenant",
    summary="租戶詳情",
    status_code=200,
)
async def get_tenant(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.get_tenant(tenantId)


@router.post(
    "/platform/tenants/{tenantId}:suspend",
    operation_id="suspendPlatformTenant",
    summary="停用租戶(平台層標示)",
    status_code=200,
)
async def suspend_tenant(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.suspend(tenant_id=tenantId, actor_user_id=user.user_id)


@router.post(
    "/platform/tenants/{tenantId}:reactivate",
    operation_id="reactivatePlatformTenant",
    summary="恢復租戶",
    status_code=200,
)
async def reactivate_tenant(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.reactivate(tenant_id=tenantId, actor_user_id=user.user_id)


# ── CR-0166 R3：License / 模組開通管理 ───────────────────────────────────────
@router.get(
    "/platform/tenants/{tenantId}/license",
    operation_id="getPlatformTenantLicense",
    summary="租戶 License 與已開通模組",
    status_code=200,
)
async def get_tenant_license(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.get_license(tenantId)


@router.put(
    "/platform/tenants/{tenantId}/license",
    operation_id="updatePlatformTenantLicense",
    summary="更新租戶 License（訂閱級距／模組開通／到期日）",
    status_code=200,
)
async def update_tenant_license(
    body: LicenseUpdateBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.update_license(
        tenant_id=tenantId, plan_tier=body.plan_tier,
        entitled_modules=body.entitled_modules,
        license_expires_at=body.license_expires_at, actor_user_id=user.user_id)
