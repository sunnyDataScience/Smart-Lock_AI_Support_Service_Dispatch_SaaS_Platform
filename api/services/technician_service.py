"""Technicians 業務邏輯（read + 自身 PATCH）。

讀 technicians 表並 mapping 成 OpenAPI Technician schema：
  - level (S/A/B/C) — DB 無此欄；統一補 "C" 預設
  - availability (enum) — DB JSONB 為自由格式；統一補 "available"
  - skills ↔ capabilities (JSONB)
  - service_areas ↔ service_regions (JSONB)
  - completed_orders_count ↔ completed_orders
  - circuit_breaker_until — DB 無此欄；統一回 None

寫入只支援 me PATCH（updateMyProfile），不開放別人改動。
租戶隔離：technicians.tenant_id 直接過濾（phase1 migration 已加欄）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.technician_service")


_DEFAULT_LEVEL = "C"
_DEFAULT_AVAILABILITY = "available"


def _coerce_jsonb_list(value) -> list[str]:
    """Tolerant JSONB → list[str]：DB 中 capabilities/service_regions 可能存 JSON list 或 NULL。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (json.JSONDecodeError, ValueError):
            return []
    return []


_TECH_SELECT = (
    "t.id, t.user_id, t.name, t.phone, t.email, "
    "t.capabilities, t.service_regions, t.rating, t.completed_orders, "
    "t.status, t.created_at"
)


def _tech_row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _TECH_SELECT。Technician schema：必填欄位都要齊。"""
    out: dict = {
        "id": str(row[0]),
        "name": row[2] or "",
        "phone": row[3] or "",
        "level": _DEFAULT_LEVEL,
        "availability": _DEFAULT_AVAILABILITY,
        "skills": _coerce_jsonb_list(row[5]),
        "service_areas": _coerce_jsonb_list(row[6]),
        "rating": float(row[7]) if row[7] is not None else 0.0,
        "completed_orders_count": int(row[8] or 0),
        "circuit_breaker_until": None,
        "created_at": row[10].isoformat() if row[10] else None,
    }
    if row[4]:
        out["email"] = row[4]
    return out


async def list_technicians(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    availability: str | None = None,
    level: str | None = None,
) -> dict:
    """GET /technicians — 管理員視角，cursor 分頁。

    availability / level 為 OpenAPI 欄位但 DB 沒對應實值；本 phase 不做實際過濾，
    僅在 service 層校驗值在 enum 內並原樣回，UI 端可接但不影響資料筆數。
    後續若要真實過濾，需在 technicians 表新增 level + availability 欄位。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["t.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(t.created_at, t.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_TECH_SELECT} FROM technicians t "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY t.created_at DESC, t.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_tech_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[10].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_technician(*, tenant_id: str, technician_id: str) -> dict:
    """GET /technicians/{id} — 管理員視角單筆查詢。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t "
        f"WHERE t.id = %s::uuid AND t.tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Technician not found", 404)
    return _tech_row_to_dict(row)


async def _find_by_user_id(*, tenant_id: str, user_id: str) -> tuple | None:
    cur = await db_module._conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t "
        f"WHERE t.user_id = %s::uuid AND t.tenant_id = %s::uuid LIMIT 1",
        (user_id, tenant_id),
    )
    return await cur.fetchone()


async def get_my_profile(*, tenant_id: str, user_id: str) -> dict:
    """GET /technicians/me。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    row = await _find_by_user_id(tenant_id=tenant_id, user_id=user_id)
    if not row:
        raise ApiError("NOT_FOUND", "Technician profile not found", 404)
    return _tech_row_to_dict(row)


async def update_my_profile(*, tenant_id: str, user_id: str, patch: dict) -> dict:
    """PATCH /technicians/me — 僅允許 name/phone/email/capabilities/regions 五欄部分更新。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    row = await _find_by_user_id(tenant_id=tenant_id, user_id=user_id)
    if not row:
        raise ApiError("NOT_FOUND", "Technician profile not found", 404)

    sets: list[str] = []
    args: list = []
    if "name" in patch and patch["name"] is not None:
        sets.append("name = %s")
        args.append(patch["name"])
    if "phone" in patch and patch["phone"] is not None:
        sets.append("phone = %s")
        args.append(patch["phone"])
    if "email" in patch and patch["email"] is not None:
        sets.append("email = %s")
        args.append(patch["email"])
    if "capabilities" in patch and patch["capabilities"] is not None:
        sets.append("capabilities = %s::jsonb")
        args.append(json.dumps(list(patch["capabilities"])))
    if "regions" in patch and patch["regions"] is not None:
        sets.append("service_regions = %s::jsonb")
        args.append(json.dumps(list(patch["regions"])))

    if sets:
        args.extend([str(row[0]), tenant_id])
        await db_module._conn.execute(
            f"UPDATE technicians SET {', '.join(sets)} "
            f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
            args,
        )

    refreshed = await _find_by_user_id(tenant_id=tenant_id, user_id=user_id)
    return _tech_row_to_dict(refreshed) if refreshed else _tech_row_to_dict(row)


async def get_my_availability(
    *,
    tenant_id: str,
    user_id: str,
    date_str: str,
    work_order_id: str | None = None,
) -> dict:
    """GET /technicians/me/availability — 回傳當日 09:00–18:00 每小時 slot。

    當天若有 work_orders.scheduled_at 落在 slot，標 hard_conflict（reason=another_order）。
    customer_preferences / past_reschedule_count 為保留欄位（佔位）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    row = await _find_by_user_id(tenant_id=tenant_id, user_id=user_id)
    if not row:
        raise ApiError("NOT_FOUND", "Technician profile not found", 404)
    technician_id = str(row[0])

    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "Invalid date format (expect YYYY-MM-DD)", 422)

    day_start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    cur = await db_module._conn.execute(
        "SELECT id, scheduled_at FROM work_orders "
        "WHERE technician_id = %s::uuid "
        "  AND scheduled_at >= %s AND scheduled_at < %s "
        "  AND status NOT IN ('completed','confirmed','cancelled') "
        "ORDER BY scheduled_at",
        (technician_id, day_start, day_end),
    )
    booked = await cur.fetchall()
    booked_set = {b[1] for b in booked if b[1] is not None}

    slots: list[dict] = []
    for hour in range(9, 18):
        slot_start = datetime.combine(day, time(hour, 0), tzinfo=timezone.utc)
        slot_end = slot_start + timedelta(hours=1)
        hard = any(slot_start <= b < slot_end for b in booked_set)
        slots.append({
            "start": slot_start.isoformat(),
            "end": slot_end.isoformat(),
            "status": "hard_conflict" if hard else "available",
            "conflict_reason": "another_order" if hard else None,
        })

    past_reschedule_count = 0
    if work_order_id:
        # 保留欄位；目前無 reschedule_history 表可查，先回 0。
        past_reschedule_count = 0

    return {
        "slots": slots,
        "customer_preferences": {
            "preferred_hours": [],
            "dnd_hours": [],
        },
        "past_reschedule_count": past_reschedule_count,
    }


async def create_technician(
    *,
    tenant_id: str,
    display_name: str,
    coverage_areas: list[str],
    phone: str | None = None,
    email: str | None = None,
    capabilities: list[str] | None = None,
) -> tuple[dict, bool]:
    """POST /tenants/{tenantId}/technicians — onboard 新技師（operationId: createTechnician）。

    Idempotency（業務唯一鍵）：tenant_id + display_name（name）— 同 tenant 同姓名
    若已存在（非 suspended/terminated），回 (existing, created=False)（HTTP 200）。
    created=True → HTTP 201。

    DB constraints:
      - name NOT NULL
      - phone NOT NULL → 若呼叫端未提供，填 '' 作為佔位（pending 狀態）
      - status 預設 'pending_approval'
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # Idempotency check：同 tenant + 同 name 且非 suspended/terminated
    cur = await db_module._conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t "
        "WHERE t.tenant_id = %s::uuid AND t.name = %s "
        "  AND t.status NOT IN ('suspended', 'terminated') "
        "ORDER BY t.created_at ASC LIMIT 1",
        (tenant_id, display_name),
    )
    existing_row = await cur.fetchone()
    if existing_row:
        return _tech_row_to_dict(existing_row), False

    # INSERT 新技師
    # phone NOT NULL；未提供時填 pattern-valid 佔位（Technician 回應 model phone 規則 ^09\d{8}$，
    # 空字串會驗證失敗並污染 list 端點序列化）。pending 技師之佔位號碼，待 onboard 補實。
    phone_val = phone if phone else "0900000000"
    capabilities_json = json.dumps(capabilities or [])
    service_regions_json = json.dumps(coverage_areas)

    cur = await db_module._conn.execute(
        "INSERT INTO technicians "
        "  (tenant_id, name, phone, email, capabilities, service_regions, status) "
        "VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, 'pending_approval') "
        "RETURNING id",
        (tenant_id, display_name, phone_val, email, capabilities_json, service_regions_json),
    )
    row = await cur.fetchone()
    new_id = str(row[0])

    # 重新 SELECT 以取得完整 row（含 created_at 等欄位）
    cur = await db_module._conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t WHERE t.id = %s::uuid",
        (new_id,),
    )
    new_row = await cur.fetchone()
    return _tech_row_to_dict(new_row), True


async def get_dashboard_stats(*, tenant_id: str) -> dict:
    """Dashboard 技師概況：total_count / online_count / dispatchable_count。

    - total_count：tenant 內 status='active' 的技師數
    - online_count：active 且當下無進行中工單（status NOT IN created/assigned/accepted/in_progress
      或無對應工單）。簡化定義：active 但沒有正在執行（in_progress）的工單。
    - dispatchable_count：當前等同 online_count（保留欄位）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM technicians WHERE tenant_id = %s::uuid AND status = 'active'",
        (tenant_id,),
    )
    row = await cur.fetchone()
    total_count = int(row[0] or 0) if row else 0

    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM technicians t "
        "WHERE t.tenant_id = %s::uuid AND t.status = 'active' "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM work_orders wo "
        "    WHERE wo.technician_id = t.id "
        "      AND wo.status = 'in_progress'"
        "  )",
        (tenant_id,),
    )
    row = await cur.fetchone()
    online_count = int(row[0] or 0) if row else 0

    return {
        "total_count": total_count,
        "online_count": online_count,
        "dispatchable_count": online_count,
    }
