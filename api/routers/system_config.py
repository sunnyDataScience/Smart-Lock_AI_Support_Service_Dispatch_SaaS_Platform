"""System Config router — 2 endpoints (getSystemConfig, updateSystemConfig)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.deps import CurrentUser, role_required
from core.idempotency import idempotency_guard, IdempotencyContext
from models.generated import SystemConfig
from services import config_service

router = APIRouter()


@router.get(
    "/config",
    operation_id="getSystemConfig",
    summary="取得系統設定",
    response_model=SystemConfig,
)
async def get_system_config(
    user: CurrentUser = Depends(role_required("admin", "reviewer")),
) -> SystemConfig:
    cfg = await config_service.get_config(user.tenant_id)
    return SystemConfig(**cfg)


@router.patch(
    "/config",
    operation_id="updateSystemConfig",
    summary="更新系統設定（部分更新）",
    response_model=SystemConfig,
)
async def update_system_config(
    body: SystemConfig,
    user: CurrentUser = Depends(role_required("admin")),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> SystemConfig:
    patch = body.model_dump(exclude_none=True)
    merged = await config_service.update_config(user.tenant_id, patch, updated_by=user.user_id)
    payload = SystemConfig(**merged)
    if idem is not None:
        await idem.save(200, payload.model_dump(mode="json"))
    return payload
