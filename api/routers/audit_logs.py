"""Audit Logs router — listAuditLogs + exportAuditEvents endpoints。

operationId 對齊 openapi.yaml：listAuditLogs / exportAuditEvents
讀 audit_events 表（部署層級事件，不做 tenant 過濾）。
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from models.generated import AuditLogEntry, AuditLogPage, AuditLogType
from services import audit_log_service
from services.audit_log_service import (
    EXPORT_CSV_COLUMNS,
    SYNC_EXPORT_THRESHOLD,
)

logger = logging.getLogger("api.routers.audit_logs")

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


# ─────────────────────────────────────────────────────────────────────────────
# Export — F-020 / E7x §4.2 P1
# ─────────────────────────────────────────────────────────────────────────────


class ExportAuditEventsRequest(BaseModel):
    """Filter payload for POST /audit-logs/export.

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
    """Serialize a single record as one CSV line.

    csv.writer auto-quotes fields containing commas / quotes / newlines, which
    matters for the JSON-encoded `payload` column.
    """
    buf = io.StringIO()
    csv.writer(buf).writerow([record.get(col, "") for col in EXPORT_CSV_COLUMNS])
    return buf.getvalue()


def _filename(now: datetime, ext: str) -> str:
    return f"audit-events-{now.strftime('%Y-%m-%d-%H%M')}.{ext}"


@router.post(
    "/audit-logs/export",
    operation_id="exportAuditEvents",
    summary="匯出稽核事件為 CSV",
    responses={
        200: {
            "description": "CSV / JSON stream（同步）",
            "content": {"text/csv": {}, "application/json": {}},
        },
        202: {"description": "Background job（>100k 筆，待後續實作）"},
    },
)
async def export_audit_events(
    body: ExportAuditEventsRequest,
    request: Request,
    user: CurrentUser = Depends(require_tenant),
):
    # Authorization: only admin / ops roles may export.  Other roles get a
    # generic 403 — exposing the rule list would leak the RBAC matrix.
    if user.role not in {"admin", "ops"}:
        raise ApiError(
            error_code="FORBIDDEN",
            message="audit.read.all permission required to export audit events",
            status_code=403,
        )

    # Estimate row count to choose sync vs async path.
    total = await audit_log_service.count_audit_events(
        from_=body.from_,
        to=body.to,
        event_types=body.event_types or None,
        actor_id=body.actor_id,
        resource_type=body.resource_type,
    )

    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client else None

    # Audit the export request itself (best-effort, never blocks).
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
        },
        ip_address=client_ip,
    )

    # Async path — TODO: queue a background job + email notification with
    # signed download URL.  For now we surface a 202 with a stub job_id so
    # the contract holds and clients can implement polling.
    if total > SYNC_EXPORT_THRESHOLD:
        job_id = str(uuid.uuid4())
        # TODO: enqueue actual export job; for now this is a contract-only stub.
        return {
            "job_id": job_id,
            "estimated_completion": None,
        }

    # Sync path — stream rows out as the cursor walks the table so memory
    # stays bounded regardless of total row count (within the threshold).
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
                # Strip the JSON-encoded payload column back to a dict so the
                # JSON response stays structured (CSV needs string, JSON does not).
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
