"""Audit Logs router — listAuditLogs endpoint。

operationId 對齊 openapi.yaml：listAuditLogs
讀 audit_events 表（部署層級事件，不做 tenant 過濾）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import AuditLogEntry, AuditLogPage, AuditLogType
from services import audit_log_service

router = APIRouter()


@router.get(
    "/audit-logs",
    operation_id="listAuditLogs",
    summary="稽核日誌列表（cursor 分頁）",
    response_model=AuditLogPage,
)
async def list_audit_logs(
    log_type: AuditLogType | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await audit_log_service.list_audit_logs(
        log_type=log_type.value if log_type else None,
        start_time=start_time,
        end_time=end_time,
        actor_id=actor_id,
        cursor=cursor,
        limit=limit,
    )
    return {
        "items": [AuditLogEntry(**e).model_dump(mode="json") for e in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
