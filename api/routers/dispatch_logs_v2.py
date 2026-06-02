"""Dispatch Logs v2 router — tenant-scoped 派工歷程查詢（read-only）。

對齊 frozen spec §2.2 M06 DispatchLogs（read-only slice）：
  - GET  /tenants/{tenantId}/dispatch-logs        → listDispatchLogsV2（cursor 分頁）
  - GET  /tenants/{tenantId}/dispatch-logs/{id}   → getDispatchLogV2

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - admin-only（dispatch-logs 為監控用途，非一般 operator 介面）
  - 呼既有 dispatch_log_service 函式，不重寫 SQL
  - 舊 flat 路徑 /api/v1/dispatch-logs（routers/dispatch_logs.py）仍保留，
    加掛 Deprecation header（D3）雙掛過渡；前端遷移後於 P3 波次移除。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, role_required
from core.errors import ApiError
from models.generated import (
    DispatchAction,
    DispatchLog,
    DispatchLogPage,
)
from services import dispatch_log_service

router = APIRouter()

# dispatch-logs 為管理員監控派工歷程介面；僅限 admin / operations_manager
_DISPATCH_LOGS_ROLES = ("admin", "operations_manager", "tenant_admin")


@router.get(
    "/tenants/{tenantId}/dispatch-logs",
    operation_id="listDispatchLogsV2",
    summary="派工歷程列表 v2（tenant-scoped，cursor 分頁，admin-only）",
    response_model=DispatchLogPage,
    tags=["M06 Dispatch"],
)
async def list_dispatch_logs_v2(
    tenantId: str = Path(...),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    work_order_id: str | None = Query(default=None),
    action: DispatchAction | None = Query(default=None),
    user: CurrentUser = Depends(role_required(*_DISPATCH_LOGS_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    page = await dispatch_log_service.list_dispatch_logs(
        tenant_id=tenantId,
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


@router.get(
    "/tenants/{tenantId}/dispatch-logs/{id}",
    operation_id="getDispatchLogV2",
    summary="派工歷程詳情 v2（tenant-scoped，admin-only）",
    tags=["M06 Dispatch"],
)
async def get_dispatch_log_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_LOGS_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    log = await dispatch_log_service.get_dispatch_log(
        tenant_id=tenantId,
        log_id=id,
    )
    return {"data": DispatchLog(**log).model_dump(mode="json")}
