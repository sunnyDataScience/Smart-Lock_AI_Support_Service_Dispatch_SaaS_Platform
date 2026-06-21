"""Monthly Settlement v2 router — CR-0012 Stage 2 endpoints (HD-1 Manual CSV)。

5 endpoints (tenant-scoped)：
  1. POST  /tenants/{tenantId}/accounting/monthly-settlements:generate
            → 觸發 generate_monthly_batch（HD-2 cron 或 admin manual）
  2. GET   /tenants/{tenantId}/accounting/monthly-settlements/{batchId}
            → 看 batch summary
  3. GET   /tenants/{tenantId}/accounting/monthly-settlements/{batchId}/csv
            → 下載 CSV (text/csv)
  4. POST  /tenants/{tenantId}/accounting/monthly-settlements/{batchId}:mark-exported
            → 標 CSV 已給財務（HD-1 V1 path）
  5. POST  /tenants/{tenantId}/accounting/settlements/{settlementId}:mark-manual-paid
            → admin UI 標 manual_paid + 上傳水單（HD-4）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import monthly_settlement_service as svc

logger = logging.getLogger("api.monthly_settlements_v2")

router = APIRouter()


async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


# ─────────────────────────────────────────────────────────────────────────────
# Bodies
# ─────────────────────────────────────────────────────────────────────────────

class GenerateBatchBody(BaseModel):
    period_year: int
    period_month: int  # 1-12
    triggered_by: str | None = "manual"  # cron / manual


class MarkExportedBody(BaseModel):
    csv_url: str | None = None  # GCS object URL


class MarkManualPaidBody(BaseModel):
    receipt_url: str
    note: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST :generate
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/monthly-settlements:generate",
    operation_id="generateMonthlySettlementBatch",
    summary="觸發月結批次（HD-2 cron 或 admin manual）— 冪等",
    response_model=dict,
    status_code=201,
)
async def generate_batch(
    body: GenerateBatchBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    batch = await svc.generate_monthly_batch(
        tenant_id=tenantId,
        period_year=body.period_year,
        period_month=body.period_month,
        triggered_by=body.triggered_by or "manual",
    )
    payload = {"data": batch}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET batch
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/accounting/monthly-settlements/{batchId}",
    operation_id="getMonthlySettlementBatch",
    summary="取月結 batch summary",
    response_model=dict,
)
async def get_batch(
    tenantId: str = Path(...),
    batchId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _guard_tenant(user, tenantId)
    return {"data": await svc._get_batch(batchId)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET CSV
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/accounting/monthly-settlements/{batchId}/csv",
    operation_id="exportMonthlySettlementBatchCSV",
    summary="下載月結 CSV（HD-1 V1 manual file flow）",
    response_class=PlainTextResponse,
)
async def export_csv(
    tenantId: str = Path(...),
    batchId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> PlainTextResponse:
    _guard_tenant(user, tenantId)
    csv_text = await svc.export_batch_csv(batch_id=batchId, tenant_id=tenantId)
    filename = f"monthly-settlement-{batchId[:8]}.csv"
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST :mark-exported
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/monthly-settlements/{batchId}:mark-exported",
    operation_id="markMonthlySettlementBatchExported",
    summary="標 CSV 已給財務 (HD-1 V1)；settlement pending → csv_exported",
    response_model=dict,
)
async def mark_exported(
    body: MarkExportedBody,
    tenantId: str = Path(...),
    batchId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.mark_csv_exported(
        batch_id=batchId, tenant_id=tenantId, csv_url=body.csv_url,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST settlement :mark-manual-paid (HD-4)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tenants/{tenantId}/accounting/settlements/{settlementId}:mark-manual-paid",
    operation_id="markSettlementManualPaid",
    summary="admin UI 確認 manual 撥款 + 上傳水單 (HD-4)",
    response_model=dict,
)
async def mark_manual_paid(
    body: MarkManualPaidBody,
    tenantId: str = Path(...),
    settlementId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.mark_manual_paid(
        settlement_id=settlementId,
        tenant_id=tenantId,
        actor_id=initiator,
        receipt_url=body.receipt_url,
    )
    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload
