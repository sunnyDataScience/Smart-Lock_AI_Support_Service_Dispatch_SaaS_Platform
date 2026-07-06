"""Technician Certification v2 router — 技能認證矩陣「唯讀」（CR-0104 → CR-0114 收斂）。

師傅詳情頁「技能認證矩陣」真資料來源。本檔只留讀端點：
  - GET /tenants/{tenantId}/technicians/{techId}/certifications → 列認證

**寫端點已於 CR-0114 收斂輪移除**（認證屬師傅身分域資質，歸平台方職權）：
  - POST createTechnicianCertification / PATCH updateTechnicianCertification /
    DELETE deleteTechnicianCertification → 廢止。認證登錄途徑=3001 /tech-register
    自助註冊時填報；平台方認證管理功能為後續輪（platform console）。

設計原則對齊 technicians_v2：require_tenant + cross-tenant guard（ADR-0030）、
envelope { data }。路徑多一層 literal `certifications` 段，與 /technicians/{techId} 不衝突。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import technician_certification_service as cert_service

router = APIRouter()


def _guard_tenant(user: CurrentUser, tenant_id: str, write: bool) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


@router.get(
    "/tenants/{tenantId}/technicians/{techId}/certifications",
    operation_id="listTechnicianCertifications",
    summary="技師認證列表（tenant-scoped，admin 視角）",
    tags=["M05 Technician"],
)
async def list_certifications(
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId, write=False)
    items = await cert_service.list_certifications(
        tenant_id=tenantId, technician_id=techId
    )
    return {"data": items}
