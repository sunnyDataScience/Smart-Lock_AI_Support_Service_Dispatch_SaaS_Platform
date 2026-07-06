"""Platform console 師傅審核 router(CR-0114 R3)。

裁決 1:師傅生命週期審核搬到平台方。全部 gate = require_platform_admin
(非 tenant-scoped);initiator 取已驗簽 token sub(廢除品牌端的自報
X-Initiator header,無偽造面)。

- GET  /platform/technicians?status=&q=
- POST /platform/technicians/{id}:onboard-approve / :onboard-reject /
                                  :suspend / :reactivate / :terminate
- GET  /platform/technicians/lifecycle-events?tech_id=&event_type=
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_platform_admin
from models.generated import Technician, TechnicianLevel
from services import platform_technician_service as svc

logger = logging.getLogger("api.routers.platform_technicians")
router = APIRouter()


class ApproveBody(BaseModel):
    notes: str | None = None


class ReasonBody(BaseModel):
    reason: str
    notes: str | None = None


class TechnicianCreateBody(BaseModel):
    """平台手動 onboard 新師傅（對齊舊品牌 createTechnician 欄位）。"""

    display_name: str = Field(..., description="師傅顯示姓名")
    coverage_areas: list[str] = Field(..., description="服務覆蓋區域")
    phone: str | None = Field(default=None, description="聯絡電話（選填）")
    email: str | None = Field(default=None, description="電子郵件（選填）")
    capabilities: list[str] | None = Field(default=None, description="可服務品牌/技能碼")


class TechnicianUpdateBody(BaseModel):
    """編輯師傅主檔（部分更新，皆選填）。"""

    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    coverage_areas: list[str] | None = None
    capabilities: list[str] | None = None
    level: TechnicianLevel | None = None


class CertCreateBody(BaseModel):
    cert_name: str = Field(..., description="認證項目名稱")
    brand: str | None = None
    obtained_at: str | None = None
    expires_at: str | None = None


class CertUpdateBody(BaseModel):
    cert_name: str | None = None
    brand: str | None = None
    obtained_at: str | None = None
    expires_at: str | None = None


@router.get(
    "/platform/technicians",
    operation_id="listPlatformTechnicians",
    summary="跨品牌師傅清單(平台審核用)",
    status_code=200,
)
async def list_technicians(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_technicians(status=status, q=q)


@router.post(
    "/platform/technicians/{technicianId}:onboard-approve",
    operation_id="platformApproveTechnician",
    summary="師傅核准(pending_approval → active)",
    status_code=200,
)
async def approve(
    body: ApproveBody | None = None,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.approve_onboarding(
        tech_id=technicianId, actor_user_id=user.user_id,
        notes=(body.notes if body else None),
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:onboard-reject",
    operation_id="platformRejectTechnician",
    summary="師傅拒絕(pending_approval → rejected)",
    status_code=200,
)
async def reject(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.reject_onboarding(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:suspend",
    operation_id="platformSuspendTechnician",
    summary="師傅停權(active → suspended)",
    status_code=200,
)
async def suspend(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.suspend(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:reactivate",
    operation_id="platformReactivateTechnician",
    summary="師傅復權(suspended → active)",
    status_code=200,
)
async def reactivate(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.reactivate(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.post(
    "/platform/technicians/{technicianId}:terminate",
    operation_id="platformTerminateTechnician",
    summary="師傅終止(任何 → terminated 終態)",
    status_code=200,
)
async def terminate(
    body: ReasonBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    result = await svc.terminate(
        tech_id=technicianId, actor_user_id=user.user_id,
        reason=body.reason, notes=body.notes,
    )
    return {"data": result}


@router.get(
    "/platform/technicians/lifecycle-events",
    operation_id="listPlatformTechnicianLifecycleEvents",
    summary="跨品牌師傅 lifecycle audit",
    status_code=200,
)
async def list_lifecycle_events(
    tech_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await svc.list_lifecycle_events(
        tech_id=tech_id, event_type=event_type, limit=limit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 師傅管理（CR-0114 §8 追補收尾：建立/詳情/編輯/認證維護移到 platform console）
# 全部 gate = require_platform_admin。放在 lifecycle-events 之後 → literal segment
# 不被 {technicianId} catch-all 攔截。
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/platform/technicians",
    operation_id="platformCreateTechnician",
    summary="平台手動 onboard 新師傅（pending_approval，待核准）",
    status_code=201,
)
async def create_technician(
    body: TechnicianCreateBody,
    response: Response,
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    technician, created = await svc.create_technician(
        display_name=body.display_name,
        coverage_areas=body.coverage_areas,
        phone=body.phone,
        email=body.email,
        capabilities=body.capabilities,
    )
    response.status_code = 201 if created else 200
    return {"data": Technician(**technician).model_dump(mode="json")}


@router.get(
    "/platform/technicians/{technicianId}",
    operation_id="getPlatformTechnician",
    summary="師傅詳情（身分域 + authorized_brands）",
    status_code=200,
)
async def get_technician(
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    technician = await svc.get_technician_detail(tech_id=technicianId)
    # Technician schema 不含 authorized_brands（會被 ignore）→ merge 回去供平台詳情顯示。
    data = Technician(**technician).model_dump(mode="json")
    data["authorized_brands"] = technician.get("authorized_brands", [])
    return {"data": data}


@router.patch(
    "/platform/technicians/{technicianId}",
    operation_id="updatePlatformTechnician",
    summary="編輯師傅主檔（name/phone/email/capabilities/regions/level）",
    status_code=200,
)
async def update_technician(
    body: TechnicianUpdateBody,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    patch = {
        "name": body.display_name,
        "phone": body.phone,
        "email": body.email,
        "capabilities": body.capabilities,
        "regions": body.coverage_areas,
        "level": body.level.value if body.level else None,
    }
    technician = await svc.update_technician(tech_id=technicianId, patch=patch)
    return {"data": Technician(**technician).model_dump(mode="json")}


@router.get(
    "/platform/technicians/{technicianId}/certifications",
    operation_id="listPlatformTechnicianCertifications",
    summary="師傅認證列表",
    status_code=200,
)
async def list_certifications(
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    items = await svc.list_certifications(tech_id=technicianId)
    return {"data": items}


@router.post(
    "/platform/technicians/{technicianId}/certifications",
    operation_id="createPlatformTechnicianCertification",
    summary="新增師傅認證",
    status_code=201,
)
async def create_certification(
    body: CertCreateBody,
    response: Response,
    technicianId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    cert = await svc.create_certification(
        tech_id=technicianId, cert_name=body.cert_name, brand=body.brand,
        obtained_at=body.obtained_at, expires_at=body.expires_at,
    )
    response.status_code = 201
    return {"data": cert}


@router.patch(
    "/platform/technicians/{technicianId}/certifications/{certId}",
    operation_id="updatePlatformTechnicianCertification",
    summary="編輯師傅認證",
    status_code=200,
)
async def update_certification(
    body: CertUpdateBody,
    technicianId: str = Path(...),
    certId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    cert = await svc.update_certification(
        tech_id=technicianId, cert_id=certId,
        patch=body.model_dump(exclude_unset=True),
    )
    return {"data": cert}


@router.delete(
    "/platform/technicians/{technicianId}/certifications/{certId}",
    operation_id="deletePlatformTechnicianCertification",
    summary="刪除師傅認證",
    status_code=200,
)
async def delete_certification(
    technicianId: str = Path(...),
    certId: str = Path(...),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    await svc.delete_certification(tech_id=technicianId, cert_id=certId)
    return {"data": None}
