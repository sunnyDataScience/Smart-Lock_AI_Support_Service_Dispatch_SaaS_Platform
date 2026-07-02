"""技師排班 + 在線狀態 service。

對應 endpoints：
  GET    /api/v1/technicians/me/schedule?month=YYYY-MM
  POST   /api/v1/technicians/me/schedule/leave-request
  POST   /api/v1/technicians/me/schedule/standby-request
  DELETE /api/v1/technicians/me/schedule/request/{id}
  PATCH  /api/v1/technicians/me/availability

對應 SQL：SQL/Schema_tech_schedule.sql
  - technicians.online_state（available/busy/offline/on_leave/circuit_breaker_open）
  - technician_schedule_requests（leave/standby pending → approved/rejected/cancelled）
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.technician_schedule_service")

_VALID_AVAILABILITY = {
    "available",
    "busy",
    "offline",
    "on_leave",
    "circuit_breaker_open",
}
_VALID_TYPES = {"leave", "standby"}
_CANCELLABLE_STATUSES = {"pending"}


# =============================================================================
# Online state (PATCH /technicians/me/availability)
# =============================================================================


async def update_my_online_state(
    *, tenant_id: str, user_id: str, online_state: str
) -> dict:
    """切換在線狀態。回傳更新後的 technician profile（含 online_state）。"""
    if online_state not in _VALID_AVAILABILITY:
        raise ApiError(
            "VALIDATION_ERROR",
            f"online_state must be one of {sorted(_VALID_AVAILABILITY)}",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE technicians SET online_state = %s, updated_at = NOW() "
        "WHERE user_id = %s::uuid AND tenant_id = %s::uuid "
        "RETURNING id, name, online_state",
        (online_state, user_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Technician not found", 404)
    return {
        "id": str(row[0]),
        "name": row[1],
        "online_state": row[2],
    }


# =============================================================================
# Monthly schedule (GET /technicians/me/schedule?month=YYYY-MM)
# =============================================================================


def _parse_month(month_str: str) -> tuple[date, date]:
    """YYYY-MM → (first_day, last_day_exclusive)"""
    try:
        y, m = month_str.split("-")
        year = int(y)
        month = int(m)
        if not 1 <= month <= 12 or year < 2020 or year > 2100:
            raise ValueError("out of range")
    except (ValueError, AttributeError) as e:
        raise ApiError(
            "VALIDATION_ERROR",
            "month must be in YYYY-MM format",
            422,
        ) from e
    first = date(year, month, 1)
    last = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first, last


async def get_my_schedule(
    *, tenant_id: str, user_id: str, month_str: str
) -> dict:
    """回傳該月份的排班資訊：每日工單數 + 休假/備勤標記 + 待審核申請。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    first, last_excl = _parse_month(month_str)

    # 1) 取得該技師當月每日工單數量
    cur = await db_module._conn.execute(
        "SELECT DATE(wo.scheduled_at) AS day, COUNT(*) "
        "FROM work_orders wo "
        "JOIN technicians t ON t.id = wo.technician_id "
        "WHERE t.user_id = %s::uuid AND t.tenant_id = %s::uuid "
        "  AND wo.scheduled_at >= %s AND wo.scheduled_at < %s "
        "  AND wo.status NOT IN ('cancelled') "
        "GROUP BY DATE(wo.scheduled_at)",
        (user_id, tenant_id, first, last_excl),
    )
    rows = await cur.fetchall()
    work_orders_per_day: dict[str, int] = {
        r[0].isoformat(): int(r[1]) for r in rows
    }

    # 2) 取得該月份內已核准的休假/備勤
    cur = await db_module._conn.execute(
        "SELECT type, start_date, end_date FROM technician_schedule_requests "
        "WHERE technician_user_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status = 'approved' "
        "  AND start_date < %s AND end_date >= %s",
        (user_id, tenant_id, last_excl, first),
    )
    approved = await cur.fetchall()
    leave_days: set[str] = set()
    standby_days: set[str] = set()
    for r in approved:
        type_, s, e = r[0], r[1], r[2]
        d = max(s, first)
        end = min(e, date(last_excl.year, last_excl.month, 1))
        while d < last_excl and d <= e:
            (leave_days if type_ == "leave" else standby_days).add(d.isoformat())
            d = date.fromordinal(d.toordinal() + 1)

    # 3) 取得待審核申請
    cur = await db_module._conn.execute(
        "SELECT id, type, start_date, end_date, reason, status, created_at "
        "FROM technician_schedule_requests "
        "WHERE technician_user_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status = 'pending' "
        "ORDER BY created_at DESC",
        (user_id, tenant_id),
    )
    pending = await cur.fetchall()
    pending_requests = [
        {
            "id": str(r[0]),
            "type": r[1],
            "start_date": r[2].isoformat(),
            "end_date": r[3].isoformat(),
            "reason": r[4],
            "status": r[5],
            "created_at": (
                r[6].isoformat() if isinstance(r[6], datetime) else str(r[6])
            ),
        }
        for r in pending
    ]

    return {
        "month": month_str,
        "work_orders_per_day": work_orders_per_day,
        "leave_days": sorted(leave_days),
        "standby_days": sorted(standby_days),
        "pending_requests": pending_requests,
    }


async def get_schedule_for_technician(
    *, tenant_id: str, tech_id: str, month_str: str
) -> dict:
    """admin 視角：依 technicians.id 取某技師當月排班（2026-07-02 師傅測試修復）。

    後台技師詳情頁「本週排班」原為 hardcoded mock；本函式讓其接真資料。
    工單數直接以 technician_id 統計（不經 user_id，容忍 user_id 為 NULL 的
    展示用技師）；休假/備勤走 technician_schedule_requests（user_id 為 NULL
    時自然為空）。不回 pending_requests（審核在技師自助流程處理）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    first, last_excl = _parse_month(month_str)

    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (tech_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Technician not found", 404)
    user_id = str(row[0]) if row[0] else None

    cur = await db_module._conn.execute(
        "SELECT DATE(wo.scheduled_at) AS day, COUNT(*) "
        "FROM work_orders wo "
        "WHERE wo.technician_id = %s::uuid "
        "  AND wo.scheduled_at >= %s AND wo.scheduled_at < %s "
        "  AND wo.status NOT IN ('cancelled') "
        "GROUP BY DATE(wo.scheduled_at)",
        (tech_id, first, last_excl),
    )
    rows = await cur.fetchall()
    work_orders_per_day = {r[0].isoformat(): int(r[1]) for r in rows}

    leave_days: set[str] = set()
    standby_days: set[str] = set()
    if user_id:
        cur = await db_module._conn.execute(
            "SELECT type, start_date, end_date FROM technician_schedule_requests "
            "WHERE technician_user_id = %s::uuid AND tenant_id = %s::uuid "
            "  AND status = 'approved' "
            "  AND start_date < %s AND end_date >= %s",
            (user_id, tenant_id, last_excl, first),
        )
        approved = await cur.fetchall()
        for r in approved:
            type_, s, e = r[0], r[1], r[2]
            d = max(s, first)
            while d < last_excl and d <= e:
                (leave_days if type_ == "leave" else standby_days).add(d.isoformat())
                d = date.fromordinal(d.toordinal() + 1)

    return {
        "month": month_str,
        "work_orders_per_day": work_orders_per_day,
        "leave_days": sorted(leave_days),
        "standby_days": sorted(standby_days),
    }


# =============================================================================
# Create schedule request (leave / standby)
# =============================================================================


async def create_schedule_request(
    *,
    tenant_id: str,
    user_id: str,
    request_type: Literal["leave", "standby"],
    start_date_str: str,
    end_date_str: str,
    reason: str,
) -> dict:
    if request_type not in _VALID_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"type must be one of {sorted(_VALID_TYPES)}",
            422,
        )
    try:
        s = date.fromisoformat(start_date_str)
        e = date.fromisoformat(end_date_str)
    except ValueError as exc:
        raise ApiError(
            "VALIDATION_ERROR",
            "start_date / end_date must be YYYY-MM-DD",
            422,
        ) from exc
    if e < s:
        raise ApiError(
            "VALIDATION_ERROR",
            "end_date must be on/after start_date",
            422,
        )
    if len(reason.strip()) < 5:
        raise ApiError(
            "VALIDATION_ERROR",
            "reason must be at least 5 characters",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "INSERT INTO technician_schedule_requests "
        "  (technician_user_id, tenant_id, type, start_date, end_date, reason) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s) "
        "RETURNING id, type, start_date, end_date, reason, status, created_at",
        (user_id, tenant_id, request_type, s, e, reason.strip()),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError(
            "INTERNAL", "Failed to create schedule request", 500
        )
    return {
        "id": str(row[0]),
        "type": row[1],
        "start_date": row[2].isoformat(),
        "end_date": row[3].isoformat(),
        "reason": row[4],
        "status": row[5],
        "created_at": (
            row[6].isoformat() if isinstance(row[6], datetime) else str(row[6])
        ),
    }


# =============================================================================
# Cancel pending request (DELETE)
# =============================================================================


async def cancel_schedule_request(
    *, tenant_id: str, user_id: str, request_id: str
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM technician_schedule_requests "
        "WHERE id = %s::uuid AND technician_user_id = %s::uuid AND tenant_id = %s::uuid",
        (request_id, user_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Schedule request not found", 404)
    if row[0] not in _CANCELLABLE_STATUSES:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot cancel request in status '{row[0]}'; only 'pending' allowed",
            409,
        )
    await db_module._conn.execute(
        "UPDATE technician_schedule_requests SET "
        "  status = 'cancelled', resolved_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (request_id,),
    )
    return {"id": request_id, "status": "cancelled"}


# =============================================================================
# Admin endpoints (list pending / approve / reject)
# =============================================================================


_RESOLVABLE_STATUSES = {"pending"}


async def list_schedule_requests(
    *,
    tenant_id: str,
    status: str | None = None,
    type_filter: str | None = None,
    limit: int = 50,
) -> dict:
    """admin 列表所有 tenant 內排班申請（可依 status/type 過濾）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    where = ["sr.tenant_id = %s::uuid"]
    params: list = [tenant_id]
    if status:
        where.append("sr.status = %s")
        params.append(status)
    if type_filter:
        where.append("sr.type = %s")
        params.append(type_filter)
    params.append(limit)
    sql = (
        "SELECT sr.id, sr.type, sr.start_date, sr.end_date, sr.reason, "
        "       sr.status, sr.created_at, sr.resolved_at, sr.resolution_note, "
        "       sr.technician_user_id, t.name "
        "FROM technician_schedule_requests sr "
        "LEFT JOIN technicians t ON t.user_id = sr.technician_user_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY sr.created_at DESC LIMIT %s"
    )
    cur = await db_module._conn.execute(sql, tuple(params))
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "type": r[1],
            "start_date": r[2].isoformat(),
            "end_date": r[3].isoformat(),
            "reason": r[4],
            "status": r[5],
            "created_at": (
                r[6].isoformat() if isinstance(r[6], datetime) else str(r[6])
            ),
            "resolved_at": (
                r[7].isoformat() if isinstance(r[7], datetime) else None
            ),
            "resolution_note": r[8],
            "technician_user_id": str(r[9]),
            "technician_name": r[10],
        }
        for r in rows
    ]
    return {"items": items}


async def resolve_schedule_request(
    *,
    tenant_id: str,
    resolver_user_id: str,
    request_id: str,
    decision: Literal["approved", "rejected"],
    note: str | None = None,
) -> dict:
    """approve / reject pending request。"""
    if decision not in {"approved", "rejected"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be 'approved' or 'rejected'",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status FROM technician_schedule_requests "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (request_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Schedule request not found", 404)
    if row[0] not in _RESOLVABLE_STATUSES:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot resolve request in status '{row[0]}'; only 'pending' allowed",
            409,
        )
    cur = await db_module._conn.execute(
        "UPDATE technician_schedule_requests SET "
        "  status = %s, "
        "  resolver_user_id = %s::uuid, "
        "  resolution_note = %s, "
        "  resolved_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid "
        "RETURNING id, type, start_date, end_date, reason, status, created_at, resolved_at, technician_user_id",
        (decision, resolver_user_id, note, request_id),
    )
    r = await cur.fetchone()
    if not r:
        raise ApiError("INTERNAL", "Failed to update request", 500)
    result = {
        "id": str(r[0]),
        "type": r[1],
        "start_date": r[2].isoformat(),
        "end_date": r[3].isoformat(),
        "reason": r[4],
        "status": r[5],
        "created_at": r[6].isoformat() if isinstance(r[6], datetime) else str(r[6]),
        "resolved_at": (
            r[7].isoformat() if isinstance(r[7], datetime) else None
        ),
        "resolution_note": note,
    }
    technician_user_id = str(r[8])

    # 寫 notifications 表（持久化）+ 透過 WS hub 即時推給技師（best-effort）
    try:
        await _notify_schedule_resolved(
            tenant_id=tenant_id,
            technician_user_id=technician_user_id,
            request=result,
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_schedule_resolved failed (non-fatal)")

    return result


async def _notify_schedule_resolved(
    *, tenant_id: str, technician_user_id: str, request: dict
) -> None:
    """approve/reject 後通知該技師。寫 notifications 表 + WS hub 即時推送。"""
    type_label = "休假" if request["type"] == "leave" else "備勤"
    decision_label = "已核准" if request["status"] == "approved" else "已拒絕"
    severity = "info" if request["status"] == "approved" else "warning"
    title = f"{type_label}申請{decision_label}"
    body = (
        f"{request['start_date']} ~ {request['end_date']} 的{type_label}申請"
        f"{decision_label}"
    )
    if request.get("resolution_note"):
        body += f"。備註：{request['resolution_note']}"

    # 寫入 notifications 表（fallback：前端 polling 也能拿到）
    notif_id = None
    try:
        import uuid as _uuid

        notif_id = str(_uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO notifications "
            "  (id, tenant_id, user_id, type, severity, title, body, source) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, 'system', %s, %s, %s, 'system')",
            (notif_id, tenant_id, technician_user_id, severity, title, body),
        )
    except Exception:  # noqa: BLE001
        logger.exception("insert notification row failed (non-fatal)")

    # 即時推送到該技師的 WS channel
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            f"/realtime/notifications/{technician_user_id}",
            {
                "type": "notification",
                "payload": {
                    "id": notif_id,
                    "type": "system",
                    "severity": severity,
                    "title": title,
                    "body": body,
                    "source": "system",
                    "created_at": datetime.now().isoformat(),
                    "related_entity": {
                        "type": "schedule_request",
                        "id": request["id"],
                        "url": "/account/schedule",
                    },
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish failed (non-fatal)")
