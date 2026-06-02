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

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard

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
