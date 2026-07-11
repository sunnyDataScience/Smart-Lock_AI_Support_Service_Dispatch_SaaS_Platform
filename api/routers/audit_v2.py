"""Audit v2 router — tenant-scoped 稽核事件端點（CR-0002-α 雙掛過渡）。

v2 path 對齊 frozen spec (gap audit §2.2)：
  GET  /tenants/{tenantId}/audit/events   → listAuditEventsV2
  POST /tenants/{tenantId}/audit/exports  → exportAuditEventsV2

舊 /api/v1/audit-logs + /api/v1/audit-logs/export 保留並加 Deprecation header（D3）。
業務邏輯直接呼叫既有 audit_log_service 函式，不重寫。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field

from core.deps import FULL_ACCESS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from models.generated import AuditLogEntry, AuditLogPage, AuditLogType
from services import audit_log_service
from services.audit_log_service import (
    EXPORT_CSV_COLUMNS,
    SYNC_EXPORT_THRESHOLD,
)
import csv
import io
import uuid
from datetime import timezone
from fastapi.responses import StreamingResponse

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# GET /tenants/{tenantId}/audit/events
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/audit/events",
    operation_id="listAuditEventsV2",
    summary="稽核事件列表（tenant-scoped v2，cursor 分頁）",
    response_model=AuditLogPage,
)
async def list_audit_events_v2(
    tenantId: str = Path(...),
    log_type: AuditLogType | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

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


@router.get(
    "/tenants/{tenantId}/audit/verify",
    operation_id="verifyAuditChainV2",
    summary="稽核 hash-chain 完整性驗證（NFR-Aud-001；偵測竄改/斷鏈）",
)
async def verify_audit_chain_v2(
    tenantId: str = Path(...),
    limit: int = Query(default=1000, ge=1, le=10000),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    """CR-0164 A：把既有 audit_log_service.verify_audit_chain 接上 API（原為死機制）。

    audit_events 為部署層級事件（無 tenant_id），鏈為全域——tenant path 僅供
    授權對齊（admin gate + ADR-0030 cross-tenant guard）；驗的是整條部署鏈。
    回 {checked, valid, broken_at}；valid=False 時 broken_at 為第一個竄改/斷鏈列 id。
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    result = await audit_log_service.verify_audit_chain(limit=limit)
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# POST /tenants/{tenantId}/audit/exports
# ─────────────────────────────────────────────────────────────────────────────

class ExportAuditEventsV2Request(BaseModel):
    """Filter payload for POST /tenants/{tenantId}/audit/exports.

    `from_` aliased to `from` because `from` is a Python keyword; pydantic
    handles the alias both ways via `populate_by_name`.
    """

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    event_types: list[str] = Field(default_factory=list)
    actor_id: str | None = None
    resource_type: str | None = None
    format: Literal["csv", "json"] = "csv"

    model_config = {"populate_by_name": True}


def _csv_header_row() -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(EXPORT_CSV_COLUMNS)
    return buf.getvalue()


def _csv_row(record: dict) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow([record.get(col, "") for col in EXPORT_CSV_COLUMNS])
    return buf.getvalue()


def _filename(now: datetime, ext: str) -> str:
    return f"audit-events-{now.strftime('%Y-%m-%d-%H%M')}.{ext}"


@router.post(
    "/tenants/{tenantId}/audit/exports",
    operation_id="exportAuditEventsV2",
    summary="匯出稽核事件（tenant-scoped v2）",
    responses={
        200: {
            "description": "CSV / JSON stream（同步）",
            "content": {"text/csv": {}, "application/json": {}},
        },
        202: {"description": "Background job（>100k 筆，待後續實作）"},
    },
)
async def export_audit_events_v2(
    body: ExportAuditEventsV2Request,
    request: Request,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
):
    # cross-tenant guard
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    # Authorization: only admin / ops roles may export.
    if user.role not in {"admin", "ops"}:
        raise ApiError(
            error_code="FORBIDDEN",
            message="audit.read.all permission required to export audit events",
            status_code=403,
        )

    total = await audit_log_service.count_audit_events(
        from_=body.from_,
        to=body.to,
        event_types=body.event_types or None,
        actor_id=body.actor_id,
        resource_type=body.resource_type,
    )

    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client else None

    await audit_log_service.log_event(
        event_type="admin_action",
        actor_id=user.user_id,
        actor_role=user.role,
        action="audit.export.requested",
        target_type="audit_events",
        target_id=None,
        payload={
            "filters": body.model_dump(mode="json", by_alias=True),
            "estimated_rows": total,
            "format": body.format,
            "tenant_id": tenantId,
        },
        ip_address=client_ip,
    )

    if total > SYNC_EXPORT_THRESHOLD:
        job_id = str(uuid.uuid4())
        return {
            "job_id": job_id,
            "estimated_completion": None,
        }

    if body.format == "json":
        async def gen_json():
            yield "["
            first = True
            async for record in audit_log_service.stream_audit_events(
                from_=body.from_,
                to=body.to,
                event_types=body.event_types or None,
                actor_id=body.actor_id,
                resource_type=body.resource_type,
            ):
                import json as _json

                payload = record.get("payload") or ""
                rec_out = {**record}
                if payload:
                    try:
                        rec_out["payload"] = _json.loads(payload)
                    except _json.JSONDecodeError:
                        rec_out["payload"] = None
                else:
                    rec_out["payload"] = None
                chunk = _json.dumps(rec_out, ensure_ascii=False)
                if first:
                    first = False
                    yield chunk
                else:
                    yield "," + chunk
            yield "]"

        return StreamingResponse(
            gen_json(),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{_filename(now, "json")}"'
                ),
            },
        )

    async def gen_csv():
        yield _csv_header_row()
        async for record in audit_log_service.stream_audit_events(
            from_=body.from_,
            to=body.to,
            event_types=body.event_types or None,
            actor_id=body.actor_id,
            resource_type=body.resource_type,
        ):
            yield _csv_row(record)

    return StreamingResponse(
        gen_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_filename(now, "csv")}"'
            ),
        },
    )
