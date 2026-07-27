"""ADR-036：平台管理員操作 S2S principal/credential 生命週期。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_platform_admin
from core.errors import ApiError
from services import service_credential_service as service

router = APIRouter()

CredentialGrant = Annotated[
    str,
    Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-zA-Z0-9*][a-zA-Z0-9:._*-]*$",
    ),
]


def _action_id(value: str | None) -> str:
    if not value:
        raise ApiError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required", 400)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ApiError(
            "IDEMPOTENCY_KEY_INVALID", "Idempotency-Key must be a UUID", 400
        ) from exc


class PrincipalCreateBody(BaseModel):
    name: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    description: str | None = Field(default=None, max_length=500)
    audiences: list[CredentialGrant] = Field(min_length=1, max_length=10)
    scopes: list[CredentialGrant] = Field(min_length=1, max_length=50)
    allowed_tenant_ids: list[UUID] = Field(default_factory=list, max_length=500)
    allow_all_tenants: bool = False
    credential_expires_at: datetime


class RotateBody(BaseModel):
    expires_at: datetime
    overlap_seconds: int = Field(default=0, ge=0, le=86400)


class RevokeBody(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.get(
    "/platform/service-principals",
    operation_id="listServicePrincipals",
    summary="列出服務主體（永不回傳 credential secret/hash）",
)
async def list_service_principals(
    _user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {"data": await service.list_principals()}


@router.post(
    "/platform/service-principals",
    operation_id="createServicePrincipal",
    summary="建立服務主體並一次性簽發第一把 credential",
    status_code=201,
)
async def create_service_principal(
    body: PrincipalCreateBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    data = await service.create_principal(
        name=body.name,
        description=body.description,
        audiences=list(dict.fromkeys(body.audiences)),
        scopes=list(dict.fromkeys(body.scopes)),
        allowed_tenant_ids=[str(item) for item in body.allowed_tenant_ids],
        allow_all_tenants=body.allow_all_tenants,
        expires_at=body.credential_expires_at,
        actor_id=user.user_id,
        action_id=_action_id(idempotency_key),
    )
    return {"data": data}


@router.post(
    "/platform/service-credentials/{credential_id}:rotate",
    operation_id="rotateServiceCredential",
    summary="輪替 credential；新 secret 僅回傳一次，舊 credential 依 overlap 到期",
)
async def rotate_service_credential(
    credential_id: UUID,
    body: RotateBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {
        "data": await service.rotate_credential(
            credential_id=str(credential_id),
            expires_at=body.expires_at,
            actor_id=user.user_id,
            action_id=_action_id(idempotency_key),
            overlap_seconds=body.overlap_seconds,
        )
    }


@router.post(
    "/platform/service-credentials/{credential_id}:revoke",
    operation_id="revokeServiceCredential",
    summary="撤銷 credential",
)
async def revoke_service_credential(
    credential_id: UUID,
    body: RevokeBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_platform_admin),
) -> dict:
    return {
        "data": await service.revoke_credential(
            credential_id=str(credential_id),
            reason=body.reason,
            actor_id=user.user_id,
            action_id=_action_id(idempotency_key),
        )
    }
