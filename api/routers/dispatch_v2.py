"""Dispatch v2 router — tenant-scoped 派工端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M06 Dispatch（colon-action 風格）：
  - GET  /tenants/{tenantId}/dispatch:candidates  → listDispatchCandidatesV2
  - POST /tenants/{tenantId}/dispatch:auto-match  → planDispatchAutoMatchV2
  - POST /tenants/{tenantId}/dispatch:plan        → planDispatchV2（FR-0003 / ADR-0045）

舊 flat 路徑（routers/dispatch.py）仍保留，加掛 Deprecation header（D3）雙掛過渡；
前端遷移後於 P3 波次移除。

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - 呼既有 dispatch_service 函式，不重寫業務邏輯
  - `:plan` colon-action 慣例：路徑含動詞短語，POST 語義
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import DISPATCH_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    DispatchAssignRequest,
    DispatchAutoMatchRequest,
    DispatchAutoMatchResponse,
    WorkOrder,
    WorkOrderEnvelope,
)
from pydantic import BaseModel, Field

from services import audit_log_service, dispatch_mode_service, dispatch_service

router = APIRouter()

# POST /tenants/{tenantId}/dispatch:plan — FR-0003/ADR-0045
# 與 legacy POST /dispatch/assign 相同角色白名單
_PLAN_ALLOWED_ROLES = (
    "admin",
    "operations_manager",
    "dispatcher",
    "customer_service",
)
_BYPASS_ROLES = {"customer_service"}


@router.get(
    "/tenants/{tenantId}/dispatch:candidates",
    operation_id="listDispatchCandidatesV2",
    summary="查詢候選技師 v2（tenant-scoped，A37 派工人工介入）",
    tags=["M06 Dispatch"],
)
async def list_dispatch_candidates_v2(
    tenantId: str = Path(...),
    work_order_id: str = Query(...),
    skills: list[str] | None = Query(default=None),
    areas: list[str] | None = Query(default=None),
    levels: list[str] | None = Query(default=None),
    exclude_circuit: bool = Query(default=True),
    rating_min: float | None = Query(default=None, ge=0.0, le=5.0),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await dispatch_service.list_dispatch_candidates(
        tenant_id=tenantId,
        work_order_id=work_order_id,
        skills_filter=skills,
        areas_filter=areas,
        levels_filter=levels,
        exclude_circuit=exclude_circuit,
        rating_min=rating_min,
    )


@router.get(
    "/tenants/{tenantId}/dispatch:candidate-detail",
    operation_id="getDispatchCandidateDetailV2",
    summary="候選技師詳情 v2（A37 派工 drawer 用，含工單脈絡 + 負載熱圖）",
    tags=["M06 Dispatch"],
)
async def get_dispatch_candidate_detail_v2(
    tenantId: str = Path(...),
    work_order_id: str = Query(...),
    technician_id: str = Query(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """A37 派工人工介入 — drawer 顯示單一候選詳細資料。"""
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await dispatch_service.get_candidate_detail(
        tenant_id=tenantId,
        work_order_id=work_order_id,
        technician_id=technician_id,
    )


@router.post(
    "/tenants/{tenantId}/dispatch:auto-match",
    operation_id="planDispatchAutoMatchV2",
    summary="依問題卡自動匹配候選技師 v2（tenant-scoped，top-N）",
    response_model=DispatchAutoMatchResponse,
    tags=["M06 Dispatch"],
)
async def plan_dispatch_auto_match_v2(
    body: DispatchAutoMatchRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES, fail_closed=True)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    urgency_str = (
        body.urgency.value if body.urgency and hasattr(body.urgency, "value") else (body.urgency or "normal")
    )
    result = await dispatch_service.auto_match_dispatch(
        tenant_id=tenantId,
        problem_card_id=str(body.problem_card_id),
        urgency=urgency_str,
        max_candidates=body.max_candidates or 3,
    )
    if idem is not None:
        await idem.save(200, result)
    return result


@router.post(
    "/tenants/{tenantId}/dispatch:plan",
    operation_id="planDispatchV2",
    summary="統一派工規劃（tenant-scoped，assign 語義）v2（FR-0003 / ADR-0045）",
    response_model=WorkOrderEnvelope,
    tags=["M06 Dispatch"],
)
async def plan_dispatch_v2(
    body: DispatchAssignRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*_PLAN_ALLOWED_ROLES, fail_closed=True)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """POST /tenants/{tenantId}/dispatch:plan — 指定技師接單（assign 統一入口）。

    語義對齊 legacy POST /dispatch/assign（FR-0003），以 tenant-scoped path 暴露。
    呼既有 dispatch_service.assign_dispatch，不重寫業務邏輯。
    客服角色（customer_service）繞過自動派工時，強制寫入稽核軌跡（ADR-0045 §4）。
    """
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    order = await dispatch_service.assign_dispatch(
        tenant_id=tenantId,
        work_order_id=str(body.work_order_id),
        technician_id=str(body.technician_id),
        override_reason=body.override_reason,
    )

    # 客服繞過自動派工 → 稽核軌跡（ADR-0045 §4 / PM Q6=A）
    if user.role in _BYPASS_ROLES:
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="manual_dispatch_bypass",
            target_type="work_order",
            target_id=str(body.work_order_id),
            payload={
                "endpoint": "planDispatchV2",
                "technician_id": str(body.technician_id),
                "override_reason": body.override_reason or "未提供理由",
            },
        )

    payload = {"data": WorkOrder(**order).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# CR-0030 派工模式切換（manual / platform_paid / auto_match）
# ---------------------------------------------------------------------------


class _DispatchModeBody(BaseModel):
    """設定租戶派工模式。"""

    mode: str = Field(description="manual / platform_paid / auto_match")


@router.get(
    "/tenants/{tenantId}/dispatch-mode",
    operation_id="getDispatchModeV2",
    summary="取得租戶派工模式 v2（CR-0030）",
    tags=["M06 Dispatch"],
)
async def get_dispatch_mode_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId does not match authenticated tenant", 403)
    mode = await dispatch_mode_service.get_dispatch_mode(tenantId)
    return {"tenant_id": tenantId, "dispatch_mode": mode}


@router.post(
    "/tenants/{tenantId}/dispatch-mode",
    operation_id="setDispatchModeV2",
    summary="切換租戶派工模式 v2（CR-0030；管理角色）",
    tags=["M06 Dispatch"],
)
async def set_dispatch_mode_v2(
    body: _DispatchModeBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required("admin", "operations_manager")),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId does not match authenticated tenant", 403)
    result = await dispatch_mode_service.set_dispatch_mode(tenant_id=tenantId, mode=body.mode)
    try:
        await audit_log_service.log_event(
            event_type="dispatch_mode_switched", actor_id=user.user_id,
            actor_role=user.role, action=f"set_dispatch_mode:{body.mode}",
            target_type="tenant", target_id=tenantId, payload={"mode": body.mode},
        )
    except Exception:  # noqa: BLE001 — audit best-effort
        pass
    return result
