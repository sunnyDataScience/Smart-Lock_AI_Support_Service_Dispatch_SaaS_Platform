"""Settlements v2 router — tenant-scoped 月結觸發端點（M12 / FR-0012）。

spec（frozen V1.1 openapi.yaml）:
  POST /tenants/{tenantId}/settlements/monthly → triggerMonthlySettlement

CR-0035（金流結算收尾）:
  POST /settlements/monthly 由 501 stub **接通**既有 CR-0012 月結批次服務
  （monthly_settlement_service.generate_monthly_batch），回 202 + batch。
  盤點修正：技師撥款月結 CR-0012 已完整做（generate/CSV/水單）；此端點只是 frozen spec
  的觸發殼，接同一個已測 service。

legacy GET /api/v1/accounting/settlements（routers/settlements.py，listSettlements）
仍保留，路徑語意不同（list vs. trigger），不重疊，本模組不影響。

設計原則：
  - tenant-scoped path，無 /api/v1 前綴（對齊 frozen spec path）
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（POST 端點必帶，防止重複觸發）
  - 接 generate_monthly_batch（UPSERT tenant+year+month，冪等）；period 預設當月
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import OPS_ROLES, REVIEW_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import monthly_settlement_service, settlement_service

router = APIRouter()


class _MonthlyTriggerBody(BaseModel):
    period_year: int | None = Field(default=None, ge=2020, le=2100)
    period_month: int | None = Field(default=None, ge=1, le=12)


@router.post(
    "/tenants/{tenantId}/settlements/monthly",
    operation_id="triggerMonthlySettlement",
    summary="月結觸發 v2（tenant-scoped）— 接 CR-0012 generate_monthly_batch（M12 / FR-0012）",
    status_code=202,
    tags=["M12 Settlement"],
)
async def trigger_monthly_settlement(
    body: _MonthlyTriggerBody | None = None,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """月結觸發端點（CR-0035：接通既有 CR-0012 月結批次服務，不再 501）。

    cross-tenant guard（ADR-0030）：path tenantId 必須等於 JWT claim。
    idempotency_guard：帶 Idempotency-Key 的 POST 請求防重複觸發。
    period 預設當月（UTC）；body 可指定 period_year/period_month 補跑歷史月。
    底層 generate_monthly_batch 對 (tenant, year, month) UPSERT —— 重複觸發回既有 batch（冪等）。
    """
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    now = datetime.now(timezone.utc)
    year = (body.period_year if body else None) or now.year
    month = (body.period_month if body else None) or now.month
    batch = await monthly_settlement_service.generate_monthly_batch(
        tenant_id=tenantId, period_year=year, period_month=month,
        triggered_by="manual",
    )
    return {"data": batch}


# ─────────────────────────────────────────────────────────────────────────────
# GET /tenants/{tenantId}/settlements
#   CR-0008（業主裁 HD-01=last_3_months / HD-02=period_end_desc）
#   解 P3 收尾 1 caller（accounting/page.tsx:124）
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/settlements",
    operation_id="listSettlementsV2",
    summary="Settlement 列表 v2（tenant-scoped；CR-0008 預設過濾最近 3 個月 + period_end desc）",
    tags=["M12 Settlement"],
)
async def list_settlements_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    status: str | None = Query(default=None, description="pending|paid|failed"),
    technician_id: str | None = Query(default=None),
    period_filter: str = Query(
        default="last_3_months",
        description="預設 last_3_months（CR-0008 HD-01）；可選 last_12_months 或 all",
    ),
    sort_by: str = Query(
        default="period_end_desc",
        description="預設 period_end_desc（CR-0008 HD-02）；可選 created_at_desc",
    ),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # 對應 service 層的 None 語意（無篩選 / 預設 created_at sort）
    pf = None if period_filter == "all" else period_filter
    sb = None if sort_by == "created_at_desc" else sort_by

    return await settlement_service.list_settlements(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        status=status,
        technician_id=technician_id,
        period_filter=pf,
        sort_by=sb,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Batch action endpoint (POST /settlements:batch — confirm / mark_paid)
# ─────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Literal


class BatchSettlementBody(BaseModel):
    settlement_ids: list[str] = Field(..., min_length=1, max_length=200)
    action: Literal["confirm", "mark_paid"]
    payment_method: str | None = Field(default=None)
    notes: str | None = Field(default=None)


@router.post(
    "/tenants/{tenantId}/settlements:batch",
    operation_id="batchSettlementsV2",
    summary="批次操作 settlements (confirm / mark_paid)",
    response_model=dict,
)
async def batch_settlements_v2(
    body: BatchSettlementBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await settlement_service.batch_action(
        tenant_id=tenantId,
        settlement_ids=body.settlement_ids,
        action=body.action,
        payment_method=body.payment_method,
        notes=body.notes,
    )
    return {"data": result}
