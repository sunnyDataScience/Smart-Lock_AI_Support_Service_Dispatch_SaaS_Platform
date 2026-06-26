"""Technician Certification v2 router — CR-0104 技能認證矩陣（tenant-scoped）。

師傅詳情頁「技能認證矩陣」真資料來源（取代前端寫死 mock）。CRUD：
  - GET    /tenants/{tenantId}/technicians/{techId}/certifications           → 列認證
  - POST   /tenants/{tenantId}/technicians/{techId}/certifications           → 新增（admin 後台登錄）
  - PATCH  /tenants/{tenantId}/technicians/{techId}/certifications/{certId}  → 編輯
  - DELETE /tenants/{tenantId}/technicians/{techId}/certifications/{certId}  → 刪除

設計原則對齊 technicians_v2：require_tenant + cross-tenant guard（ADR-0030）、
寫操作 DISPATCH_ROLES、POST idempotency_guard、envelope { data }。
路徑多一層 literal `certifications` 段，與 /technicians/{techId} 不衝突。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Path, Response

from core.deps import DISPATCH_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import technician_certification_service as cert_service

router = APIRouter()


class _CertCreateRequest(BaseModel):
    """新增認證（cert_name 必填，其餘選填）。日期為 ISO YYYY-MM-DD 字串。"""

    cert_name: str = Field(..., description="認證項目名稱（如「電子鎖安裝認證」）")
    brand: str | None = Field(default=None, description="關聯品牌（選填）")
    obtained_at: str | None = Field(default=None, description="取得日期 YYYY-MM-DD（選填）")
    expires_at: str | None = Field(default=None, description="到期日期 YYYY-MM-DD（選填，無=無期限）")


class _CertUpdateRequest(BaseModel):
    """部分更新認證（皆選填；brand/obtained_at/expires_at 顯式傳 null 可清空）。"""

    cert_name: str | None = Field(default=None)
    brand: str | None = Field(default=None)
    obtained_at: str | None = Field(default=None)
    expires_at: str | None = Field(default=None)


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


@router.post(
    "/tenants/{tenantId}/technicians/{techId}/certifications",
    operation_id="createTechnicianCertification",
    summary="新增技師認證（admin 後台登錄）",
    status_code=201,
    tags=["M05 Technician"],
)
async def create_certification(
    body: _CertCreateRequest,
    response: Response,
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    cert = await cert_service.create_certification(
        tenant_id=tenantId,
        technician_id=techId,
        cert_name=body.cert_name,
        brand=body.brand,
        obtained_at=body.obtained_at,
        expires_at=body.expires_at,
    )
    response.status_code = 201
    payload = {"data": cert}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.patch(
    "/tenants/{tenantId}/technicians/{techId}/certifications/{certId}",
    operation_id="updateTechnicianCertification",
    summary="編輯技師認證",
    tags=["M05 Technician"],
)
async def update_certification(
    body: _CertUpdateRequest,
    tenantId: str = Path(...),
    techId: str = Path(...),
    certId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    cert = await cert_service.update_certification(
        tenant_id=tenantId,
        technician_id=techId,
        cert_id=certId,
        patch=body.model_dump(exclude_unset=True),
    )
    return {"data": cert}


@router.delete(
    "/tenants/{tenantId}/technicians/{techId}/certifications/{certId}",
    operation_id="deleteTechnicianCertification",
    summary="刪除技師認證",
    tags=["M05 Technician"],
)
async def delete_certification(
    tenantId: str = Path(...),
    techId: str = Path(...),
    certId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    await cert_service.delete_certification(
        tenant_id=tenantId, technician_id=techId, cert_id=certId
    )
    return {"data": None}
