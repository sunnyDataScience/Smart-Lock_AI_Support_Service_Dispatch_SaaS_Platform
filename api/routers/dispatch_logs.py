"""Dispatch Logs router — listDispatchLogs (read-only)。

operationId 對齊 openapi.yaml：listDispatchLogs

不含 write 路徑：dispatch_logs 由 AI 派工引擎與工單寫入流程在背景產生，
管理員介面僅讀取以監控派工歷程。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    DispatchAction,
    DispatchLog,
    DispatchLogPage,
)
from services import dispatch_log_service

router = APIRouter()


@router.get(
    "/dispatch-logs",
    operation_id="listDispatchLogs",
    summary="派工歷程列表（cursor 分頁）",
    response_model=DispatchLogPage,
)
async def list_dispatch_logs(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    work_order_id: str | None = Query(default=None),
    action: DispatchAction | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await dispatch_log_service.list_dispatch_logs(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        work_order_id=work_order_id,
        action=action.value if action else None,
    )
    return {
        "items": [DispatchLog(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
