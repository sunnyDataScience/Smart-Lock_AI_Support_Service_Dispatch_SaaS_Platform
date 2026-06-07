"""Settlements v2 router — tenant-scoped 月結觸發端點（M12 / FR-0012）。

spec（frozen V1.1 openapi.yaml）:
  POST /tenants/{tenantId}/settlements/monthly → triggerMonthlySettlement

gap-audit（docs/_audit/spec-code-gap-audit-2026-06-01.md）:
  Phase II → 回 501 stub。service 層尚無對應 monthly settlement 觸發實作。

legacy GET /api/v1/accounting/settlements（routers/settlements.py，listSettlements）
仍保留，路徑語意不同（list vs. trigger），不重疊，本模組不影響。

設計原則：
  - tenant-scoped path，無 /api/v1 前綴（對齊 frozen spec path）
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard（POST 端點必帶，防止重複觸發）
  - Phase II：501 stub，不接 service，待 M12 service 層實作後接入
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import settlement_service

router = APIRouter()


@router.post(
    "/tenants/{tenantId}/settlements/monthly",
    operation_id="triggerMonthlySettlement",
    summary="月結觸發 v2（tenant-scoped）— Phase II 501 stub（M12 / FR-0012）",
    status_code=501,
    tags=["M12 Settlement"],
)
async def trigger_monthly_settlement(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> JSONResponse:
    """月結觸發端點 — Phase II 501 stub。

    cross-tenant guard（ADR-0030）：path tenantId 必須等於 JWT claim。
    idempotency_guard：帶 Idempotency-Key 的 POST 請求防重複觸發。

    TODO（M12 monthly-settlement）:
      待 settlement_service 新增 trigger_monthly_settlement(tenant_id, period) 後接入。
      接入時移除 stub，回 202 Accepted + job_id envelope。
    """
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # Phase II stub：服務層尚未實作 monthly settlement 觸發
    return JSONResponse(
        status_code=501,
        content={
            "type": "urn:smartlock:error:not_implemented",
            "title": "Not Implemented",
            "status": 501,
            "detail": "Monthly settlement trigger is not yet implemented (Phase II stub)",
            "error_code": "NOT_IMPLEMENTED",
            "message": "Monthly settlement trigger is not yet implemented (Phase II stub)",
        },
        media_type="application/problem+json",
    )


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
    user: CurrentUser = Depends(require_tenant),
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
    user: CurrentUser = Depends(require_tenant),
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
