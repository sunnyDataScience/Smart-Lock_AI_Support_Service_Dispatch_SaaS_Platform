"""M18 Runtime Config Governance router (ADR-0067 Phase 0 / CR-0004 §8).

7 endpoints:
  1. GET  /tenants/{tenantId}/m18/configs                            → listConfigNamespaces
  2. GET  /tenants/{tenantId}/m18/configs/{namespace}/{key}          → getConfigActiveVersion
  3. PUT  /tenants/{tenantId}/m18/configs/{namespace}/{key}          → createConfigDraft   (201)
  4. POST /tenants/{tenantId}/m18/configs/{ns}/{key}/versions/{vid}:start-rollout → startConfigRollout (202)
  5. POST /tenants/{tenantId}/m18/rollouts/{rolloutId}:rollback      → rollbackConfig
  6. GET  /tenants/{tenantId}/m18/configs/{namespace}/{key}/audit    → listConfigAudit
  7. GET  /m18/config-read/{namespace}/{key}                         → readConfigAcl (flat path)

SoD (HD-06): draft requires X-Initiator only; start-rollout requires X-Initiator+X-Approver (相異).
No time-window restriction this wave (deferred per spec).

MVP scoping notes:
  - canary auto-advance (5%→50%→100%) and SLO halt: Phase II (deferred, logged in service).
  - readConfig during rolling_out conservatively returns prior active version.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from pydantic import BaseModel, Field

from core.deps import (
    FULL_ACCESS_ROLES,
    OPS_ROLES,
    CurrentUser,
    require_tenant,
    role_required,
)
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import config_m18_service as svc


def _validate_uuid(value: str, header_name: str) -> str:
    """CR-0166 R1：SoD header 須為合法 UUID（原不驗 → 假值入庫＝審計斷鏈；
    非 UUID 更會在 %s::uuid cast 爆 500）。錯誤碼統一 422（repo header 驗證慣例）。"""
    try:
        _uuid.UUID(value)
    except (ValueError, TypeError):
        raise ApiError("VALIDATION_ERROR", f"{header_name} 必須為合法 UUID", 422)
    return value

logger = logging.getLogger("api.config_m18")

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models (no matching types in generated.py)
# ─────────────────────────────────────────────────────────────────────────────

class ConfigDraft(BaseModel):
    """PUT body — create config draft."""
    proposed_value: Any = Field(..., description="待驗 namespace schema 的 config 值")
    reason: str = Field(..., min_length=1, description="變更理由")
    change_request_id: str | None = Field(default=None, description="關聯 CR id（選填）")


class RolloutRequest(BaseModel):
    """POST body — start rollout.

    observation_minutes_per_stage: default 15, hard floor 10 (HD-01).
    Values < 10 are clamped to 10 (not rejected) with an info log in service.
    """
    strategy: str = Field(..., description="canary_5_50_100 | instant")
    observation_minutes_per_stage: int = Field(
        default=15,
        ge=1,
        description="每 stage 觀察分鐘數。硬下限 10（HD-01）；< 10 被 clamp 至 10。",
    )


# ─────────────────────────────────────────────────────────────────────────────
# SoD helpers (M18-specific: only Initiator+Approver, no Executor)
# ─────────────────────────────────────────────────────────────────────────────

async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return _validate_uuid(x_initiator, "X-Initiator")


async def _require_sod_two(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
) -> tuple[str, str]:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    if not x_approver:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Approver", 422)
    if x_initiator == x_approver:
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: X-Initiator 與 X-Approver 必須不同",
            403,
        )
    return _validate_uuid(x_initiator, "X-Initiator"), _validate_uuid(x_approver, "X-Approver")


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /tenants/{tenantId}/m18/configs
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/m18/configs",
    operation_id="listConfigNamespaces",
    summary="列 config namespace 清單 (M18)",
    response_model=dict,
)
async def list_config_namespaces(
    tenantId: str = Path(...),
    namespace: str | None = Query(default=None, description="可選 namespace filter（exact match）"),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId 與 token claim 不符", 403)

    items = await svc.list_namespaces(tenantId, namespace_filter=namespace)
    return {"items": items}


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenantId}/m18/configs/{namespace}/{key}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/m18/configs/{namespace}/{key}",
    operation_id="getConfigActiveVersion",
    summary="查 (tenant,namespace,key) 的 active config version (M18)",
    response_model=dict,
)
async def get_config_active_version(
    tenantId: str = Path(...),
    namespace: str = Path(...),
    key: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId 與 token claim 不符", 403)

    result = await svc.get_active_version(tenantId, namespace, key)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. PUT /tenants/{tenantId}/m18/configs/{namespace}/{key}
# ─────────────────────────────────────────────────────────────────────────────

@router.put(
    "/tenants/{tenantId}/m18/configs/{namespace}/{key}",
    operation_id="createConfigDraft",
    summary="建 config draft（schema 驗證 + audit）(M18)",
    status_code=201,
    response_model=dict,
)
async def create_config_draft(
    body: ConfigDraft,
    tenantId: str = Path(...),
    namespace: str = Path(...),
    key: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """建 config_version(state='draft')。

    header X-Initiator required（draft 只需發起人，不強制雙簽）。
    proposed_value 先經 namespace.json_schema 驗證（422 CONFIG_SCHEMA_INVALID on fail）。
    CR-0166 R1：靜態 gate 放寬 OPS_ROLES，service 依 namespace owner_role_codes 動態縮權。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId 與 token claim 不符", 403)

    result = await svc.create_draft(
        tenant_id=tenantId,
        namespace=namespace,
        key=key,
        proposed_value=body.proposed_value,
        reason=body.reason,
        change_request_id=body.change_request_id,
        initiator_user_id=initiator,
        actor_role=user.role,
    )

    payload = result
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /tenants/{tenantId}/m18/configs/{namespace}/{key}/versions/{versionId}:start-rollout
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/m18/configs/{namespace}/{key}/versions/{versionId}:start-rollout",
    operation_id="startConfigRollout",
    summary="啟動 config rollout（SoD dual-sign，instant or canary）(M18)",
    status_code=202,
    response_model=dict,
)
async def start_config_rollout(
    body: RolloutRequest,
    tenantId: str = Path(...),
    namespace: str = Path(...),
    key: str = Path(...),
    versionId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    sod: tuple[str, str] = Depends(_require_sod_two),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """Start rollout for a draft config_version.

    Requires X-Initiator + X-Approver headers (相異 → 403 SOD_VIOLATION).

    instant: version 立即 active，dethrone 前一 active → retired。
    canary_5_50_100: version → rolling_out, stage='5%', next_stage_eta 計算。
      auto-advance (5%→50%→100%) deferred to Phase II（需 scheduler）。
      readConfig 在 rolling_out 期間回保守前一 active 版本。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId 與 token claim 不符", 403)

    initiator_uid, approver_uid = sod
    result = await svc.start_rollout(
        tenant_id=tenantId,
        namespace=namespace,
        key=key,
        version_id=versionId,
        strategy=body.strategy,
        observation_minutes=body.observation_minutes_per_stage,
        initiator_user_id=initiator_uid,
        approver_user_id=approver_uid,
        actor_role=user.role,
    )

    payload = result
    if idem is not None:
        await idem.save(202, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST /tenants/{tenantId}/m18/rollouts/{rolloutId}:rollback
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/m18/rollouts/{rolloutId}:rollback",
    operation_id="rollbackConfig",
    summary="Rollback config rollout（重啟 parent_version）(M18)",
    status_code=200,
    response_model=dict,
)
async def rollback_config(
    tenantId: str = Path(...),
    rolloutId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId 與 token claim 不符", 403)

    result = await svc.rollback(
        tenant_id=tenantId,
        rollout_id=rolloutId,
        actor_user_id=user.user_id,
    )

    payload = result
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5.5 POST /tenants/{tenantId}/m18/rollouts/{rolloutId}:slo-check (WBS §8 P1)
#     admin manual SLO halt decision — 不真 halt 只回 decision
# ─────────────────────────────────────────────────────────────────────────────

class SloCheckRequest(BaseModel):
    error_rate_pct: float = Field(..., description="觀察 error rate (5xx/total)")
    p99_latency_ms: float | None = Field(default=None)
    error_rate_slo_pct: float | None = Field(
        default=None, description="自訂門檻（不給 = 1% 預設）",
    )
    p99_latency_slo_ms: float | None = Field(
        default=None, description="自訂門檻（不給 = 1000ms 預設）",
    )


@router.post(
    "/tenants/{tenantId}/m18/rollouts/{rolloutId}:slo-check",
    operation_id="checkConfigRolloutSlo",
    summary="SLO halt decision — admin 觀察 metrics 後請求是否該 halt rollout (M18)",
    status_code=200,
    response_model=dict,
)
async def slo_check(
    body: SloCheckRequest,
    tenantId: str = Path(...),
    rolloutId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """admin 觀察線上 SLO 後請求 decision；本 endpoint 只回 should_halt 不真 halt。

    若 should_halt=true 建議：admin 顯式呼 `:rollback` 端點（避免自動 halt 風險，
    對齊 dispute 負值 resolution 人工 trail 精神）。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId 與 token claim 不符", 403)

    return await svc.check_slo_halt(
        tenant_id=tenantId,
        rollout_id=rolloutId,
        error_rate_pct=body.error_rate_pct,
        p99_latency_ms=body.p99_latency_ms,
        error_rate_slo_pct=body.error_rate_slo_pct,
        p99_latency_slo_ms=body.p99_latency_slo_ms,
        actor_user_id=user.user_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. GET /tenants/{tenantId}/m18/configs/{namespace}/{key}/audit
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/m18/configs/{namespace}/{key}/audit",
    operation_id="listConfigAudit",
    summary="列 config audit log（cursor 分頁）(M18)",
    response_model=dict,
)
async def list_config_audit(
    tenantId: str = Path(...),
    namespace: str = Path(...),
    key: str = Path(...),
    cursor: str | None = Query(default=None, description="上頁末 audit id（bigint string）"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId 與 token claim 不符", 403)

    result = await svc.list_audit(
        tenant_id=tenantId,
        namespace=namespace,
        key=key,
        cursor=cursor,
        limit=limit,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 7. GET /m18/config-read/{namespace}/{key}
#    Flat path (no tenant prefix). X-Tenant-Id header required (ADR-0030).
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/m18/config-read/{namespace}/{key}",
    operation_id="readConfigAcl",
    summary="ACL read: 取 active config value（TTL 30s cache）(M18)",
    response_model=dict,
)
async def read_config_acl(
    response: Response,
    namespace: str = Path(...),
    key: str = Path(...),
    version: str | None = Query(default=None, description="per-transaction snapshot version_id（ADR-0068）"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> dict:
    """ACL read endpoint — 給業務模組（cancellation/refund/pricing）使用。

    Header X-Tenant-ID required (ADR-0030 hard-enforce).
    ?version != active version_id → 409 CONFIG_VERSION_MISMATCH (ADR-0068).
    in-process TTL 30s cache；cache:hit|miss 在 response body。
    rolling_out 版本保守不服務（回前一 active）。

    Phase 0: endpoint + cache 建好；實際 caller 接入留各模組後續波次。
    """
    # ADR-0030 hard-enforce X-Tenant-ID
    if not x_tenant_id:
        raise ApiError(
            "VALIDATION_ERROR",
            "X-Tenant-ID header is required (ADR-0030)",
            422,
        )

    result = await svc.read_config_acl(
        tenant_id=x_tenant_id,
        namespace=namespace,
        key=key,
        requested_version_id=version,
    )

    # Set X-Config-Version response header
    response.headers["X-Config-Version"] = result["version_id"]

    return result
