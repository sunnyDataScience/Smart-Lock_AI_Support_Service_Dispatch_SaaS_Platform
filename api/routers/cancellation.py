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

from core.deps import (
    BACKOFFICE_ROLES,
    CurrentUser,
    SodActors,
    require_sod_actors,
    role_required,
)
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
    # 2026-08-02 掃描：原本只有 require_tenant（**無角色檢查**），而同一業務動作的
    # legacy 孿生端點 work_orders.py:266 早就有 role_required(*BACKOFFICE_ROLES)——
    # v2 漏掛。後果：任何該租戶的已認證帳號（technician / vendor）拿自己的 token
    # 就能取消租戶內**任一張**非終態工單，並用 client 可控的 initiator_role 與
    # goodwill_waiver 決定要不要收取消費，還會觸發後續通知與結算。
    #
    # require_sod_actors 擋不住：它只檢查 X-Initiator / X-Approver 有值且彼此相異，
    # 兩個任意字串就過，且從不比對真實使用者身分。
    #
    # ⚠️ 未修的部分：X-Initiator 仍是 client 提供的字串而非取自 token。
    # 真實身分有另外進 audit（cancellation_service 的 actor_id/actor_role），
    # 所以稽核不會被騙，但 SoD 的「發起人」欄位本身仍不可信。
    # 要改成以 token user_id 覆寫屬 SoD 設計變更，需先確認雙簽流程的意圖，另案處理。
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
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
