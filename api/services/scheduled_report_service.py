"""Scheduled Report Service — admin 報表排程 CRUD。

對應 saas.scheduled_report 表 (migration 029).
Cron 執行 (週/月/季發送 email) 由 roadmap 另立 backend cron worker
讀 is_active=true row 處理; 本 service 只負責 schedule 寫入/列出/取消.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError


_VALID_TYPES = {"kpi", "revenue", "technician_ranking", "settlements"}
_VALID_CADENCES = {"weekly", "monthly", "quarterly"}
_VALID_FORMATS = {"csv", "xlsx", "pdf"}


def _next_run(cadence: str) -> datetime:
    now = datetime.now(timezone.utc)
    if cadence == "weekly":
        return now + timedelta(days=7)
    if cadence == "monthly":
        return now + timedelta(days=30)
    return now + timedelta(days=90)  # quarterly


async def create_schedule(
    *,
    tenant_id: str,
    report_type: str,
    cadence: str,
    recipients: list[str],
    format: str = "csv",
    filters: dict | None = None,
    created_by: str | None = None,
) -> dict:
    if report_type not in _VALID_TYPES:
        raise ApiError("VALIDATION_ERROR", f"Invalid report_type: {report_type}", 422)
    if cadence not in _VALID_CADENCES:
        raise ApiError("VALIDATION_ERROR", f"Invalid cadence: {cadence}", 422)
    if format not in _VALID_FORMATS:
        raise ApiError("VALIDATION_ERROR", f"Invalid format: {format}", 422)
    if not recipients:
        raise ApiError("VALIDATION_ERROR", "recipients required", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    next_run = _next_run(cadence)
    cur = await db_module._conn.execute(
        "INSERT INTO saas.scheduled_report "
        "  (tenant_id, report_type, cadence, recipients, format, "
        "   filters, next_run_at, created_by) "
        "VALUES (%s::uuid, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s::uuid) "
        "RETURNING id, created_at",
        (
            tenant_id, report_type, cadence,
            json.dumps(recipients), format,
            json.dumps(filters) if filters else None,
            next_run, created_by,
        ),
    )
    row = await cur.fetchone()
    return {
        "id": str(row[0]),
        "tenant_id": tenant_id,
        "report_type": report_type,
        "cadence": cadence,
        "recipients": recipients,
        "format": format,
        "filters": filters,
        "next_run_at": next_run.isoformat(),
        "is_active": True,
        "created_at": row[1].isoformat() if row[1] else None,
    }


async def list_schedules(
    *,
    tenant_id: str,
    report_type: str | None = None,
    active_only: bool = True,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if report_type:
        if report_type not in _VALID_TYPES:
            raise ApiError("VALIDATION_ERROR", f"Invalid report_type: {report_type}", 422)
        where.append("report_type = %s")
        args.append(report_type)
    if active_only:
        where.append("is_active = true")

    sql = (
        "SELECT id, report_type, cadence, recipients, format, filters, "
        "       next_run_at, last_run_at, is_active, created_at "
        "FROM saas.scheduled_report "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC"
    )
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()
    items = []
    for r in rows:
        items.append({
            "id": str(r[0]),
            "report_type": r[1],
            "cadence": r[2],
            "recipients": r[3] if isinstance(r[3], list) else (json.loads(r[3]) if r[3] else []),
            "format": r[4],
            "filters": r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else None),
            "next_run_at": r[6].isoformat() if r[6] else None,
            "last_run_at": r[7].isoformat() if r[7] else None,
            "is_active": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        })
    return {"items": items}


async def cancel_schedule(
    *,
    tenant_id: str,
    schedule_id: str,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE saas.scheduled_report "
        "SET is_active = false, updated_at = NOW() "
        "WHERE tenant_id = %s::uuid AND id = %s::uuid",
        (tenant_id, schedule_id),
    )
    if cur.rowcount == 0:
        raise ApiError("NOT_FOUND", "Schedule not found", 404)
    return {"id": schedule_id, "is_active": False}
