"""Cancellation router — spec-aligned tenant-scoped 取消端點（ADR-0102 / FR-0052）。

對齊 frozen spec: openapi-smart-lock-saas.yaml
  POST /tenants/{tenantId}/work-orders/{woId}/cancel

這是 spec-alignment 第一個 vertical slice 的對外合約，示範目標架構：
  - tenant-scoped path（非 /api/v1 flat）
  - SoD headers X-Initiator / X-Approver / X-Executor（require_sod_actors）
  - 6 階段費用 + reason code 字典 + 師傅 initiated + goodwill override
  - config version snapshot + audit

舊 flat 路徑 POST /api/v1/work-orders/{id}/cancel 仍保留（thin，legacy cancel_order），
前端遷移後於波次 P2 移除。見 docs/_audit/spec-code-gap-audit-2026-06-01.md §8 C-07。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from core.deps import CurrentUser, SodActors, require_sod_actors, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.internal import CancellationEnvelope, CancellationRequest
from services import cancellation_service, config_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/cancel",
    operation_id="cancelWorkOrder6Stage",
    summary="Cancel WorkOrder — 6-stage cancellation v2 (ADR-0102)",
    response_model=CancellationEnvelope,
)
async def cancel_work_order_6stage(
    body: CancellationRequest,
    tenantId: str = Path(...),
    woId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard：path tenant 必須等於 JWT claim（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    cancellation_config, config_version = await config_service.get_cancellation_config(tenantId)

    result = await cancellation_service.cancel_work_order_6stage(
        tenant_id=tenantId,
        wo_id=woId,
        reason_code=body.reason_code,
        initiator_role=body.initiator_role,
        goodwill_waiver=body.goodwill_waiver,
        evidence_ids=body.evidence_ids,
        note=body.note,
        distance_km=body.distance_km,
        cancellation_config=cancellation_config,
        config_version=config_version,
        sod_initiator=sod.initiator,
        sod_approver=sod.approver,
        sod_executor=sod.executor,
        actor_id=user.user_id,
        actor_role=user.role,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload
