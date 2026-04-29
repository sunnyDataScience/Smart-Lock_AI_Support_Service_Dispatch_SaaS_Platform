"""Dispatch router — listDispatchCandidates。

operationId 對齊 openapi.yaml：listDispatchCandidates

未實作（將於後續 phase 補上）：
  - assignDispatch / autoMatchDispatch — 依賴規則引擎與狀態機
  - listDispatchLogs 由 routers/dispatch_logs.py 維護
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from services import dispatch_service

router = APIRouter()


@router.get(
    "/dispatch/candidates",
    operation_id="listDispatchCandidates",
    summary="查詢候選技師（A37 派工人工介入）",
)
async def list_dispatch_candidates(
    work_order_id: str = Query(...),
    skills: list[str] | None = Query(default=None),
    areas: list[str] | None = Query(default=None),
    levels: list[str] | None = Query(default=None),
    exclude_circuit: bool = Query(default=True),
    rating_min: float | None = Query(default=None, ge=0.0, le=5.0),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await dispatch_service.list_dispatch_candidates(
        tenant_id=user.tenant_id,
        work_order_id=work_order_id,
        skills_filter=skills,
        areas_filter=areas,
        levels_filter=levels,
        exclude_circuit=exclude_circuit,
        rating_min=rating_min,
    )
