"""ADR-034 三庫偏好 API。

每個 portal 只呼叫自己的權威庫；平台端不接受 X-Tenant-ID 作跨品牌授權依據。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path
from pydantic import BaseModel, Field

from core.deps import (
    BACKOFFICE_ROLES,
    CurrentUser,
    require_platform_admin,
    role_required,
)
from core.errors import ApiError
from services import preference_service

router = APIRouter()

_BRAND_PREFERENCE_ROLES = BACKOFFICE_ROLES + ("reviewer", "viewer", "vendor")
_brand_user = role_required(*_BRAND_PREFERENCE_ROLES)
_technician_user = role_required("technician")


class PreferencePutBody(BaseModel):
    value: Any
    expected_version: int = Field(ge=0)


def _required_action_id(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise ApiError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency-Key header is required",
            400,
        )
    try:
        return str(UUID(idempotency_key))
    except ValueError:
        raise ApiError(
            "IDEMPOTENCY_KEY_INVALID",
            "Idempotency-Key must be a UUID",
            400,
        )


async def _put(
    *,
    portal: preference_service.PreferencePortal,
    scope_tenant_id: str,
    preference_key: str,
    body: PreferencePutBody,
    action_id: str,
    user: CurrentUser,
) -> dict:
    data = await preference_service.put_preference(
        portal=portal,
        principal_id=user.user_id,
        scope_tenant_id=scope_tenant_id,
        preference_key=preference_key,
        value=body.value,
        expected_version=body.expected_version,
        action_id=action_id,
    )
    return {"data": data}


@router.get(
    "/tenants/{tenantId}/me/preferences",
    operation_id="listBrandUserPreferences",
    summary="列出品牌人員跨裝置偏好",
)
async def list_brand_preferences(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(_brand_user),
) -> dict:
    # role_required 已由 require_tenant 比對 path header/claim；再明列 path 防止
    # router 未來重構時把資源 scope 與 principal scope 拆開。
    if user.tenant_id != tenantId:
        raise ApiError("TENANT_MISMATCH", "Resource tenant does not match principal", 403)
    return {
        "data": await preference_service.list_preferences(
            portal="brand",
            principal_id=user.user_id,
            scope_tenant_id=tenantId,
        )
    }


@router.put(
    "/tenants/{tenantId}/me/preferences/{preferenceKey}",
    operation_id="putBrandUserPreference",
    summary="以版本 CAS 儲存品牌人員偏好",
)
async def put_brand_preference(
    body: PreferencePutBody,
    tenantId: str = Path(...),
    preferenceKey: str = Path(...),
    action_id: str = Depends(_required_action_id),
    user: CurrentUser = Depends(_brand_user),
) -> dict:
    if user.tenant_id != tenantId:
        raise ApiError("TENANT_MISMATCH", "Resource tenant does not match principal", 403)
    return await _put(
        portal="brand",
        scope_tenant_id=tenantId,
        preference_key=preferenceKey,
        body=body,
        action_id=action_id,
        user=user,
    )


@router.get(
    "/api/v2/technicians/me/preferences",
    operation_id="listTechnicianPreferences",
    summary="列出技師跨裝置偏好",
)
async def list_technician_preferences(
    user: CurrentUser = Depends(_technician_user),
) -> dict:
    return {
        "data": await preference_service.list_preferences(
            portal="tech",
            principal_id=user.user_id,
            scope_tenant_id=preference_service.ZERO_SCOPE_ID,
        )
    }


@router.put(
    "/api/v2/technicians/me/preferences/{preferenceKey}",
    operation_id="putTechnicianPreference",
    summary="以版本 CAS 儲存技師偏好",
)
async def put_technician_preference(
    body: PreferencePutBody,
    preferenceKey: str = Path(...),
    action_id: str = Depends(_required_action_id),
    user: CurrentUser = Depends(_technician_user),
) -> dict:
    return await _put(
        portal="tech",
        scope_tenant_id=preference_service.ZERO_SCOPE_ID,
        preference_key=preferenceKey,
        body=body,
        action_id=action_id,
        user=user,
    )


@router.get(
    "/api/v2/platform/me/preferences",
    operation_id="listPlatformPreferences",
    summary="列出平台管理員跨裝置偏好",
)
async def list_platform_preferences(
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {
        "data": await preference_service.list_preferences(
            portal="platform",
            principal_id=user.user_id,
            scope_tenant_id=preference_service.ZERO_SCOPE_ID,
        )
    }


@router.put(
    "/api/v2/platform/me/preferences/{preferenceKey}",
    operation_id="putPlatformPreference",
    summary="以版本 CAS 儲存平台治理偏好",
)
async def put_platform_preference(
    body: PreferencePutBody,
    preferenceKey: str = Path(...),
    action_id: str = Depends(_required_action_id),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return await _put(
        portal="platform",
        scope_tenant_id=preference_service.ZERO_SCOPE_ID,
        preference_key=preferenceKey,
        body=body,
        action_id=action_id,
        user=user,
    )
