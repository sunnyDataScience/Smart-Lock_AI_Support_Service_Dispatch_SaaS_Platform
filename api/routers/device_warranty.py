"""Device Warranty router — spec-aligned tenant-scoped 保固端點（ADR-0044 v2 / FR-0015）。

對齊 frozen spec: openapi-smart-lock-saas.yaml
  GET   /tenants/{tenantId}/devices/{deviceId}/warranty   → DeviceWarranty
  PATCH /tenants/{tenantId}/devices/{deviceId}/warranty   → 202 (manual_override)

這是 P1-B vertical slice 的對外合約，示範目標架構：
  - tenant-scoped path（非 /api/v1 flat）
  - 5-mode 起算 + period_months + B2B override 上限驗證
  - PATCH manual_override 走主管核可（SoD：X-Initiator/X-Approver），回 202

⚠ 本切片：device_warranty 獨立表尚未建（spec saas.device_warranty 留待 P3），
GET 以 5-mode 純函式 + best-effort 推算回傳；DB 來源（device / site_group）標 TODO。
PATCH 的 ChangeRequest 串接標 TODO(P3)，先回 pending 佔位 + override 上限驗證。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Response

from core.deps import CurrentUser, SodActors, require_sod_actors, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.internal import (
    DeviceWarranty,
    DeviceWarrantyEnvelope,
    DeviceWarrantyPatch,
    WarrantyChangeRequestRef,
)
from services import config_service, warranty_service

router = APIRouter()

# PATCH manual_override 至少需此角色作 approver（BR-WARRANTY-006 ≥ ops_supervisor）
_SUPERVISOR_ROLES = {"operations_manager", "operations_supervisor", "admin", "finance_manager"}


def _guard_cross_tenant(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )


@router.get(
    "/tenants/{tenantId}/devices/{deviceId}/warranty",
    operation_id="getDeviceWarranty",
    summary="Get device warranty (5-mode + start + expiry) — ADR-0044 v2",
    response_model=DeviceWarrantyEnvelope,
)
async def get_device_warranty(
    tenantId: str = Path(...),
    deviceId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_cross_tenant(user, tenantId)

    warranty_config, _version = await config_service.get_warranty_config(tenantId)

    # TODO(P3): 由 device_warranty + device 表載入真實 mode / anchor 日期 / site_group 繼承。
    # 本切片：best-effort 以 purchase_date mode（建單語意）+ 品牌 default period 推算。
    today = date.today()
    start_mode = "purchase_date"
    start_date = today
    period_months = warranty_service.resolve_period_months(None, warranty_config)
    end_date = warranty_service.compute_warranty_end(start_date, period_months)
    within = warranty_service.is_within_warranty(today, end_date)

    payload = DeviceWarranty(
        device_id=deviceId,
        warranty_start_mode=start_mode,
        warranty_start_date=start_date.isoformat(),
        warranty_end_date=end_date.isoformat(),
        warranty_period_months=period_months,
        warranty_period_months_override=None,
        warranty_scope="device",
        warranty_inherit_from_site_group=True,
        coverage_class="full" if within else "expired",
        is_within_warranty=within,
    ).model_dump(mode="json")
    return {"data": payload}


@router.patch(
    "/tenants/{tenantId}/devices/{deviceId}/warranty",
    operation_id="patchDeviceWarranty",
    summary="Adjust warranty (manual_override only; supervisor-approved) — 202",
    response_model=WarrantyChangeRequestRef,
    status_code=202,
)
async def patch_device_warranty(
    body: DeviceWarrantyPatch,
    response: Response,
    tenantId: str = Path(...),
    deviceId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_cross_tenant(user, tenantId)

    # 本切片僅支援 manual_override（spec DeviceWarrantyPatch.new_mode enum=[manual_override]）
    if body.new_mode != "manual_override":
        raise ApiError(
            "VALIDATION_ERROR",
            "PATCH warranty only supports new_mode='manual_override' in this slice",
            422,
        )

    # 主管核可：approver 角色須 ≥ ops_supervisor（BR-WARRANTY-006）。
    # SoD header 已保證 initiator ≠ approver；此處再驗 approver 為主管角色。
    if user.role not in _SUPERVISOR_ROLES:
        raise ApiError(
            "FORBIDDEN",
            f"manual_override requires supervisor role (one of {sorted(_SUPERVISOR_ROLES)})",
            403,
        )

    # B2B override 上限驗證（BR-WARRANTY-006）：> 60 → 422
    if body.period_months_override is not None:
        warranty_config, _version = await config_service.get_warranty_config(tenantId)
        warranty_service.validate_b2b_override(body.period_months_override, warranty_config)

    # TODO(P3): 建立 ChangeRequest（合約 PDF doc id + 主管 approve + audit trail），
    # 寫 warranty_claims.warranty_override_approved_by / _contract_doc_id / _approved_at。
    # 本切片先回 202 pending 佔位 — 上限驗證 + audit 欄位已就緒。
    ref = WarrantyChangeRequestRef(
        change_request_id=None,
        status="pending_supervisor_approval",
        device_id=deviceId,
        requested_mode=body.new_mode,
    ).model_dump(mode="json")

    payload = ref
    response.status_code = 202
    if idem is not None:
        await idem.save(202, payload)
    return payload
