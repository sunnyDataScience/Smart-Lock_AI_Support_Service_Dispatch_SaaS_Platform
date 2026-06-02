"""DataCorrections v2 router — tenant-scoped review queue（CR-0004 §8 / ADR-0029）。

5 endpoints（Track B S5）：
  GET  /tenants/{tenantId}/data-corrections                           → listDataCorrectionsV2
  GET  /tenants/{tenantId}/data-corrections/{correctionId}            → getDataCorrectionV2
  POST /tenants/{tenantId}/data-corrections/{correctionId}:approve    → approveDataCorrectionV2
  POST /tenants/{tenantId}/data-corrections/{correctionId}:reject     → rejectDataCorrectionV2
  POST /tenants/{tenantId}/data-corrections/{correctionId}:resolve    → resolveDataCorrectionV2

權限（HD-4）：
  list / get   → require_tenant（tenant operator 可讀）
  approve / reject / resolve → role_required("admin")（admin 才能審核）

correctionId：BIGINT（int PK，非 uuid）。

狀態機（HD-2）：
  pending → approved（approve）
  pending → rejected（reject）
  approved → resolved（resolve；SOP draft 自動建立留 phase 2，HD-3 follow-up）

cross-tenant guard（ADR-0030）：path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_*.
idempotency：approve/reject/resolve 接受 Idempotency-Key（24h dedup）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel

from core.deps import CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import data_corrections_v2_service as svc

logger = logging.getLogger("api.routers.data_corrections_v2")

router = APIRouter()

# HD-4: approve / reject / resolve 需 admin
_ADMIN_ROLES = ("admin",)


class ReviewBody(BaseModel):
    review_note: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# GET /tenants/{tenantId}/data-corrections
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/data-corrections",
    operation_id="listDataCorrectionsV2",
    summary="資料修正 review queue 列表 v2（tenant-scoped，cursor 分頁）",
    tags=["M09 Data Corrections"],
)
async def list_data_corrections_v2(
    tenantId: str = Path(...),
    status: str | None = Query(
        default=None,
        description="過濾狀態：pending / approved / resolved / rejected（空 = 全部）",
    ),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await svc.list_corrections_v2(
        tenant_id=tenantId,
        status=status or None,
        cursor=cursor,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /tenants/{tenantId}/data-corrections/{correctionId}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/data-corrections/{correctionId}",
    operation_id="getDataCorrectionV2",
    summary="資料修正詳情 v2（tenant-scoped）",
    tags=["M09 Data Corrections"],
)
async def get_data_correction_v2(
    tenantId: str = Path(...),
    correctionId: int = Path(..., description="BIGINT PK（非 uuid）"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    correction = await svc.get_correction_v2(tenant_id=tenantId, correction_id=correctionId)
    return {"data": correction}


# ─────────────────────────────────────────────────────────────────────────────
# POST /tenants/{tenantId}/data-corrections/{correctionId}:approve
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/data-corrections/{correctionId}:approve",
    operation_id="approveDataCorrectionV2",
    summary="核准資料修正 v2（pending→approved，admin-only）",
    tags=["M09 Data Corrections"],
)
async def approve_data_correction_v2(
    tenantId: str = Path(...),
    correctionId: int = Path(..., description="BIGINT PK（非 uuid）"),
    body: ReviewBody = Body(default_factory=ReviewBody),
    user: CurrentUser = Depends(role_required(*_ADMIN_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.approve_correction_v2(
        tenant_id=tenantId,
        correction_id=correctionId,
        reviewer_id=user.user_id,
        review_note=body.review_note,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# POST /tenants/{tenantId}/data-corrections/{correctionId}:reject
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/data-corrections/{correctionId}:reject",
    operation_id="rejectDataCorrectionV2",
    summary="駁回資料修正 v2（pending→rejected，admin-only）",
    tags=["M09 Data Corrections"],
)
async def reject_data_correction_v2(
    tenantId: str = Path(...),
    correctionId: int = Path(..., description="BIGINT PK（非 uuid）"),
    body: ReviewBody = Body(default_factory=ReviewBody),
    user: CurrentUser = Depends(role_required(*_ADMIN_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.reject_correction_v2(
        tenant_id=tenantId,
        correction_id=correctionId,
        reviewer_id=user.user_id,
        review_note=body.review_note,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# POST /tenants/{tenantId}/data-corrections/{correctionId}:resolve
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/data-corrections/{correctionId}:resolve",
    operation_id="resolveDataCorrectionV2",
    summary="標記資料修正已處理 v2（approved→resolved，admin-only；SOP draft 自動建立留 phase 2）",
    tags=["M09 Data Corrections"],
)
async def resolve_data_correction_v2(
    tenantId: str = Path(...),
    correctionId: int = Path(..., description="BIGINT PK（非 uuid）"),
    body: ReviewBody = Body(default_factory=ReviewBody),
    user: CurrentUser = Depends(role_required(*_ADMIN_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.resolve_correction_v2(
        tenant_id=tenantId,
        correction_id=correctionId,
        reviewer_id=user.user_id,
        review_note=body.review_note,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload
