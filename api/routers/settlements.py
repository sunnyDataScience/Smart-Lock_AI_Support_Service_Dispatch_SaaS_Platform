"""Settlements router — listSettlements (read-only)。

operationId 對齊 openapi.yaml：listSettlements

不含 listReconciliations / approveReconciliation / 退款決策等寫入路徑。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    Settlement,
    SettlementPage,
    SettlementStatus,
)
from services import settlement_service

router = APIRouter()


@router.get(
    "/accounting/settlements",
    operation_id="listSettlements",
    summary="結算記錄列表（cursor 分頁）",
    response_model=SettlementPage,
)
async def list_settlements(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: SettlementStatus | None = Query(default=None),
    technician_id: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await settlement_service.list_settlements(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        technician_id=technician_id,
    )
    return {
        "items": [Settlement(**s).model_dump(mode="json") for s in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
