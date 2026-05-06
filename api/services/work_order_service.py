"""WorkOrders 業務邏輯。

讀 work_orders 表 JOIN problem_cards 取 brand/model，mapping 成 OpenAPI schema：
  - work_orders.status (created/assigned/accepted/in_progress/completed/confirmed/cancelled)
    → WorkOrderStatus (16 enum) best-fit
  - work_orders.priority (low/normal/high/urgent) → Urgency (low/medium/high)
  - customer_address → district 解析（前綴市+區/鄉/鎮/縣）+ address 直通
  - estimated_price (FLOAT) → estimated_reward (decimal string with .2f)
  - started_at → actual_arrival（best-effort proxy；DB 沒獨立 arrival 欄位）
  - brand/model 從 problem_cards JOIN 取（DB work_orders 無此欄）

租戶隔離：透過 problem_cards JOIN conversations JOIN users.tenant_id（多 JOIN 一層）。
"""

from __future__ import annotations

import logging
import re

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor
from services.problem_card_service import _DB_URGENCY_TO_API

logger = logging.getLogger("api.work_order_service")


_DB_STATUS_TO_API = {
    "created": "inquiring",
    "assigned": "assigned",
    "accepted": "accepted",
    "in_progress": "in_progress",
    "completed": "completed",
    "confirmed": "closed",  # OpenAPI 用 closed 表示客戶已確認結案
    "cancelled": "cancelled",
}

# 「市/縣 + 區/鄉/鎮」前綴；e.g. 「新北市板橋區」/「桃園市中壢區」
_DISTRICT_RE = re.compile(r"^([\u4e00-\u9fff]+?[市縣][\u4e00-\u9fff]+?[區鄉鎮市])")


def _parse_district(addr: str | None) -> str:
    if not addr:
        return ""
    m = _DISTRICT_RE.match(addr.strip())
    return m.group(1) if m else ""


def _coerce_decimal(price) -> str | None:
    if price is None:
        return None
    return f"{float(price):.2f}"


def _coerce_status(db_status: str | None) -> str:
    if not db_status:
        return "inquiring"
    return _DB_STATUS_TO_API.get(db_status, "inquiring")


def _coerce_urgency(db_priority: str | None) -> str:
    if not db_priority:
        return "medium"
    return _DB_URGENCY_TO_API.get(db_priority, "medium")


def _wo_row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _WO_SELECT。"""
    address = row[5] or ""
    out: dict = {
        "id": str(row[0]),
        "problem_card_id": str(row[1]),
        "status": _coerce_status(row[3]),
        "district": _parse_district(address),
        "address": address,
        "brand": row[6] or "",
        "model": row[7] or "",
        "urgency": _coerce_urgency(row[4]),
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }
    if row[2] is not None:
        out["technician_id"] = str(row[2])
    reward = _coerce_decimal(row[8])
    if reward is not None:
        out["estimated_reward"] = reward
    if row[9] is not None:
        out["scheduled_time"] = row[9].isoformat()
    if row[10] is not None:
        out["actual_arrival"] = row[10].isoformat()
    if row[11] is not None:
        out["completion_time"] = row[11].isoformat()
    return out


_WO_SELECT = (
    "wo.id, wo.problem_card_id, wo.technician_id, wo.status, wo.priority, "
    "wo.customer_address, pc.brand, pc.model, "
    "wo.estimated_price, wo.scheduled_at, wo.started_at, wo.completed_at, "
    "wo.created_at, wo.updated_at"
)

_WO_JOIN = (
    "FROM work_orders wo "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "JOIN conversations c ON pc.conversation_id = c.id "
    "JOIN users u ON c.user_id = u.id"
)


async def list_orders(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    problem_card_id: str | None = None,
    technician_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if problem_card_id:
        where.append("wo.problem_card_id = %s::uuid")
        args.append(problem_card_id)

    if technician_id:
        where.append("wo.technician_id = %s::uuid")
        args.append(technician_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(wo.created_at, wo.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY wo.created_at DESC, wo.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_wo_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[12].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def list_work_order_pool(*, tenant_id: str) -> dict:
    """技師案件池：尚未進入「執行中／結案」終態的可接工單。

    含：created（未派工）、assigned（已派但尚未接受）。
    優先序：urgency=high > medium > low；同等級依 created_at ASC 列出
    （越早建立越優先）。預設不分頁，上限 100 筆。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE u.tenant_id = %s::uuid "
        f"  AND wo.status IN ('created', 'assigned') "
        f"ORDER BY "
        f"  CASE wo.priority "
        f"    WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
        f"    WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 "
        f"  END ASC, "
        f"  wo.created_at ASC, wo.id ASC "
        f"LIMIT 100"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    rows = await cur.fetchall()
    items = [_wo_row_to_dict(r) for r in rows]
    return {"items": items, "next_cursor": None, "has_more": False}


async def get_order(*, tenant_id: str, wo_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    return _wo_row_to_dict(row)


_ACCEPT_FROM = {"assigned"}
_COMPLETE_FROM = {"accepted", "in_progress"}
_CANCEL_FROM = {"created", "assigned", "accepted", "in_progress"}
_ASSIGN_FROM = {"created", "assigned"}  # 允許重派（assigned → assigned 換人）
# 升級可從任何「未結案」狀態觸發；completed/confirmed/cancelled 視為終局不可升級
_ESCALATE_FROM = {"created", "assigned", "accepted", "in_progress"}
_ESCALATE_LEVELS = {"operations_manager", "tenant_admin"}
# 客戶確認結案：只能從技師完工後的 completed 狀態進入 confirmed
_CONFIRM_FROM = {"completed"}
# 改期可從技師接單後 / 執行中觸發；created 階段尚未排程不需改期
_RESCHEDULE_FROM = {"assigned", "accepted", "in_progress"}
# 24h 內改期次數上限（業務規則：避免技師連續推遲）
_RESCHEDULE_LIMIT_24H = 3


async def _publish_and_return(
    *, tenant_id: str, wo_id: str, event_type: str
) -> dict:
    """共用：fetch 最新 order → 推 work-orders/{id} 事件 + dispatch-queue 變化通知 → 回傳。"""
    order = await get_order(tenant_id=tenant_id, wo_id=wo_id)
    try:
        from realtime.ws_hub import hub  # 延遲 import 避免循環

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": event_type,
                "payload": {"event": event_type, "work_order": order},
            },
        )
        await hub.publish(
            "/realtime/dispatch-queue",
            {
                "type": "work_order.state_change",
                "payload": {
                    "work_order_id": wo_id,
                    "event": event_type,
                    "status": order.get("status"),
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish work_order state failed (non-fatal)")
    return order


async def _fetch_status_for_update(wo_id: str, tenant_id: str) -> str:
    """Fetch current DB status with tenant guard. Raises NOT_FOUND if missing."""
    cur = await db_module._conn.execute(
        f"SELECT wo.status {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    return row[0]


async def accept_order(*, tenant_id: str, wo_id: str) -> dict:
    """assigned → accepted, set accepted_at = NOW."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ACCEPT_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot accept work order in status '{current}'; expected one of {sorted(_ACCEPT_FROM)}",
            409,
        )
    await db_module._conn.execute(
        "UPDATE work_orders SET status = 'accepted', accepted_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (wo_id,),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.accepted"
    )


async def complete_order(
    *,
    tenant_id: str,
    wo_id: str,
    summary: str,
    actual_amount: str | None = None,
) -> dict:
    """accepted | in_progress → completed, set completed_at = NOW (auto-fill started_at)."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _COMPLETE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot complete work order in status '{current}'; expected one of {sorted(_COMPLETE_FROM)}",
            409,
        )
    final_price: float | None = None
    if actual_amount is not None:
        try:
            final_price = float(actual_amount)
        except ValueError as e:
            raise ApiError("VALIDATION_ERROR", "actual_amount is not a valid decimal", 422) from e
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'completed', "
        "  completed_at = NOW(), "
        "  started_at = COALESCE(started_at, NOW()), "
        "  service_report = %s, "
        "  final_price = COALESCE(%s, final_price), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (summary, final_price, wo_id),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.completed"
    )


async def cancel_order(
    *,
    tenant_id: str,
    wo_id: str,
    reason: str | None = None,
) -> dict:
    """created | assigned | accepted | in_progress → cancelled."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _CANCEL_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot cancel work order in status '{current}'; expected non-terminal",
            409,
        )
    if reason:
        await db_module._conn.execute(
            "UPDATE work_orders SET "
            "  status = 'cancelled', "
            "  service_report = COALESCE(service_report, '') || E'\\n[CANCELLED] ' || %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid",
            (reason, wo_id),
        )
    else:
        await db_module._conn.execute(
            "UPDATE work_orders SET status = 'cancelled', updated_at = NOW() "
            "WHERE id = %s::uuid",
            (wo_id,),
        )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.cancelled"
    )


async def assign_order(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    reason_code: str,
    reason_text: str | None = None,
) -> dict:
    """created | assigned → assigned。

    驗證技師同租戶且 status='active'；附加 [ASSIGNED] 註記到 service_report。
    MVP 不執行 circuit-breaker / cross-area / skill-shortage 規則檢查（OpenAPI
    override_flags 接受但忽略），留待派工引擎模組接入後啟用。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ASSIGN_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot assign work order in status '{current}'; expected one of {sorted(_ASSIGN_FROM)}",
            409,
        )

    # Verify technician exists, same tenant, active
    cur = await db_module._conn.execute(
        "SELECT id, status FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    tech_row = await cur.fetchone()
    if not tech_row:
        raise ApiError("TECHNICIAN_NOT_FOUND", "Technician not found in this tenant", 404)
    if tech_row[1] != "active":
        raise ApiError(
            "TECHNICIAN_NOT_AVAILABLE",
            f"Technician status is '{tech_row[1]}'; only 'active' technicians can accept assignments",
            409,
        )

    note = f"[ASSIGNED:{reason_code}]"
    if reason_text:
        note += f" {reason_text}"

    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  technician_id = %s::uuid, "
        "  status = 'assigned', "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (technician_id, note, wo_id),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.assigned"
    )


async def escalate_order(
    *,
    tenant_id: str,
    wo_id: str,
    level: str,
    reason: str,
) -> dict:
    """升級工單至 operations_manager / tenant_admin。

    DB 沒有專屬升級欄位。本實作：
      - service_report append `[ESCALATED:{level}] {reason}` 留稽核軌跡
      - priority 推進到 'urgent'（若原本不是 urgent）
      - 不改 status — 升級為「上層覆審」流程，原狀態維持
    後續若上層加開 escalation_logs 表，把寫入點接過去即可。
    """
    if level not in _ESCALATE_LEVELS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"level must be one of {sorted(_ESCALATE_LEVELS)}",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ESCALATE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot escalate work order in status '{current}'; "
            f"expected one of {sorted(_ESCALATE_FROM)}",
            409,
        )

    note = f"[ESCALATED:{level}] {reason.strip()[:500]}"
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  priority = CASE WHEN priority = 'urgent' THEN priority ELSE 'urgent' END, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (note, wo_id),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.escalated"
    )


async def confirm_order(
    *,
    tenant_id: str,
    wo_id: str,
    rating: int,
    feedback: str | None = None,
) -> dict:
    """completed → confirmed，寫入客戶評分與意見，set confirmed_at = NOW()。

    rating 1-5 必填，feedback 可留空（最多 1000 字）。終局狀態 — 一旦 confirmed
    不再允許其他寫入動作（與 cancelled 並列為兩個結案形式）。
    """
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ApiError("VALIDATION_ERROR", "rating must be an integer between 1 and 5", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _CONFIRM_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm work order in status '{current}'; expected one of {sorted(_CONFIRM_FROM)}",
            409,
        )

    feedback_clean: str | None = None
    if feedback and feedback.strip():
        feedback_clean = feedback.strip()[:1000]

    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'confirmed', "
        "  confirmed_at = NOW(), "
        "  rating = %s, "
        "  feedback = COALESCE(%s, feedback), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (rating, feedback_clean, wo_id),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.confirmed"
    )


async def propose_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    proposed_slots: list[dict],
    message_to_customer: str,
    send_via: str = "line",
    warning_acknowledged_at: str | None = None,
) -> dict:
    """送出改期請求 — 取首選時段為新 scheduled_at，並把 1-3 個備選寫入稽核軌跡。

    MVP 範圍：
      - 不真的呼叫 LINE/SMS push（SOP 由派工通知模組接管）
      - 不建獨立 reschedule_slots 表（24h 內 3 次上限以 service_report 內 [RESCHEDULE] 標記計算）
      - state machine：assigned | accepted | in_progress 才允許改期
      - 首個 slot 的 start 寫入 scheduled_at 作為「假定接受」基準；客戶 RSVP 後再修正

    錯誤：
      - 422 RESCHEDULE_LIMIT_EXCEEDED：24h 內已 3 次
      - 409 STATE_CONFLICT：工單已結案 / 已取消
      - 409 RESCHEDULE_SLOT_TAKEN：首選 slot start 與其他工單衝突（同技師同時段）
    """
    if not proposed_slots or not isinstance(proposed_slots, list):
        raise ApiError("VALIDATION_ERROR", "proposed_slots is required", 422)
    if len(proposed_slots) > 3:
        raise ApiError("VALIDATION_ERROR", "proposed_slots accepts at most 3 items", 422)
    if not message_to_customer or not message_to_customer.strip():
        raise ApiError("VALIDATION_ERROR", "message_to_customer is required", 422)
    if len(message_to_customer) > 120:
        raise ApiError("VALIDATION_ERROR", "message_to_customer must be at most 120 chars", 422)
    if send_via not in {"line", "line_and_sms"}:
        raise ApiError("VALIDATION_ERROR", "send_via must be 'line' or 'line_and_sms'", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reschedule work order in status '{current}'; expected one of {sorted(_RESCHEDULE_FROM)}",
            409,
        )

    # 24h 內改期次數 — 從 service_report 計 [RESCHEDULE] 標記出現次數
    cur = await db_module._conn.execute(
        "SELECT service_report, technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    report_text = row[0] or "" if row else ""
    technician_id = row[1] if row else None
    # 簡單計數 — service_report 是 append-only，[RESCHEDULE@<iso>] 標記每次寫一筆
    import datetime as _dt
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=24)
    recent_count = 0
    for line in report_text.splitlines():
        if "[RESCHEDULE@" not in line:
            continue
        # 解 [RESCHEDULE@<iso>] 取時間戳
        try:
            iso = line.split("[RESCHEDULE@", 1)[1].split("]", 1)[0]
            ts = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=_dt.timezone.utc)
            if ts >= cutoff:
                recent_count += 1
        except (ValueError, IndexError):
            continue
    if recent_count >= _RESCHEDULE_LIMIT_24H:
        raise ApiError(
            "RESCHEDULE_LIMIT_EXCEEDED",
            f"Reschedule limit exceeded: {recent_count} times in last 24h",
            422,
        )

    # 首選 slot 的 start 作為新 scheduled_at
    first_slot = proposed_slots[0]
    new_start = first_slot.get("start")
    if not new_start:
        raise ApiError("VALIDATION_ERROR", "first proposed slot is missing 'start'", 422)

    # 同技師同時段衝突檢查（best-effort — 同 technician_id 在同 start 時間已有別張未結案工單）
    if technician_id:
        cur = await db_module._conn.execute(
            "SELECT 1 FROM work_orders "
            "WHERE technician_id = %s::uuid "
            "  AND id <> %s::uuid "
            "  AND status NOT IN ('completed','confirmed','cancelled') "
            "  AND scheduled_at = %s::timestamptz "
            "LIMIT 1",
            (str(technician_id), wo_id, new_start),
        )
        if await cur.fetchone():
            raise ApiError(
                "RESCHEDULE_SLOT_TAKEN",
                "First proposed slot conflicts with another work order assigned to the same technician",
                409,
            )

    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    slots_summary = "; ".join(
        f"{s.get('start','?')}~{s.get('end','?')}" for s in proposed_slots
    )
    note = (
        f"[RESCHEDULE@{now_iso}] via={send_via} slots={slots_summary} "
        f"msg={message_to_customer.strip()[:120]}"
    )
    if warning_acknowledged_at:
        note += f" ack={warning_acknowledged_at}"

    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_start, note, wo_id),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.rescheduled"
    )


async def get_dispatch_queue_snapshot(*, tenant_id: str) -> dict:
    """派工佇列快照：pending / assigning / assigned + sla_at_risk。

    OpenAPI 語義 → DB status mapping：
      - pending   = 'created'   工單剛建立、尚未派工
      - assigning = 'assigned'  系統已指派、等技師回應
      - assigned  = 'accepted'  技師已接受（已派工確認）
    in_progress / completed / confirmed / cancelled 均不計入派工佇列。

    sla_at_risk：尚未結案且預定時間落在「現在起 2 小時內」（含已過期），
    用一個 SQL FILTER 子句一次算完，不分窗。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT "
        f"  COUNT(*) FILTER (WHERE wo.status = 'created')  AS pending, "
        f"  COUNT(*) FILTER (WHERE wo.status = 'assigned') AS assigning, "
        f"  COUNT(*) FILTER (WHERE wo.status = 'accepted') AS assigned, "
        f"  COUNT(*) FILTER (WHERE wo.status NOT IN ('completed','confirmed','cancelled') "
        f"                     AND wo.scheduled_at IS NOT NULL "
        f"                     AND wo.scheduled_at < NOW() + INTERVAL '2 hours') AS sla_at_risk "
        f"{_WO_JOIN} "
        f"WHERE u.tenant_id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    row = await cur.fetchone()
    return {
        "pending": int(row[0] or 0) if row else 0,
        "assigning": int(row[1] or 0) if row else 0,
        "assigned": int(row[2] or 0) if row else 0,
        "sla_at_risk": int(row[3] or 0) if row else 0,
    }


async def get_today_stats(*, tenant_id: str) -> dict:
    """Dashboard 派工 KPI：今日工單數 + 完工率 + 逾時工單。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT "
        f"  COUNT(*) FILTER (WHERE wo.created_at >= date_trunc('day', NOW())) AS today_count, "
        f"  COUNT(*) FILTER (WHERE wo.created_at >= date_trunc('day', NOW()) "
        f"                     AND wo.status IN ('completed','confirmed')) AS completed_today, "
        f"  COUNT(*) FILTER (WHERE wo.status NOT IN ('completed','confirmed','cancelled') "
        f"                     AND wo.scheduled_at IS NOT NULL "
        f"                     AND wo.scheduled_at < NOW()) AS overdue_count "
        f"{_WO_JOIN} "
        f"WHERE u.tenant_id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    row = await cur.fetchone()
    today_count = int(row[0] or 0) if row else 0
    completed_today = int(row[1] or 0) if row else 0
    overdue_count = int(row[2] or 0) if row else 0
    completion_rate = (completed_today / today_count) if today_count > 0 else None
    return {
        "today_count": today_count,
        "completion_rate": completion_rate,
        "overdue_count": overdue_count,
    }


# =============================================================================
# Subflow events (T5–T8)
# =============================================================================
# 設計：以結構化標籤 prepend 到 service_report 文字欄位，避免新增 schema。
# 各事件帶 [TAG] 前綴 + ISO timestamp + JSON 序列化的細節。後續可遷移至獨立
# work_order_events 表。
#
# 對應前端：
#   /my-orders/[id]/scope-change       → POST /work-orders/{id}/scope-change
#   /my-orders/[id]/material-request   → POST /work-orders/{id}/material-request
#   /my-orders/[id]/delay              → POST /work-orders/{id}/delay
#   /my-orders/[id]/door-check         → POST /work-orders/{id}/door-check

import json
from datetime import datetime, timezone

# 子流程允許狀態：技師作業中（含 assigned 之後到 in_progress；不含 completed 後）
_SUBFLOW_FROM = {"assigned", "accepted", "in_progress"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_TAG_TO_EVENT_TYPE = {
    "SCOPE_CHANGE": "scope_change",
    "MATERIAL_REQUEST": "material_request",
    "DELAY": "delay",
    "DOOR_CHECK": "door_check",
}


async def _append_subflow_event(
    *,
    tenant_id: str,
    wo_id: str,
    tag: str,
    payload: dict,
    actor_user_id: str | None = None,
) -> dict:
    """驗 status → INSERT 一筆 work_order_events → bump updated_at → 推 WS → 回傳。

    v1.30.0 重構：從 service_report 文字 append 改為結構化事件表寫入，
    便於後續 timeline / 統計 / 稽核查詢。service_report 不再被 subflow 修改。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record {tag} in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    event_type = _TAG_TO_EVENT_TYPE.get(tag, "other")
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)",
        (
            wo_id,
            tenant_id,
            actor_user_id,
            event_type,
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    # 仍 bump updated_at 讓既有 list 排序對齊
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )
    return await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type=f"work_order.subflow.{event_type}",
    )


async def record_scope_change(
    *,
    tenant_id: str,
    wo_id: str,
    reason: str,
    items: list[dict],
    total_estimate: str | None = None,
) -> dict:
    """記錄範圍變更申請（T5）。等待客戶核准的設計目前簡化為直接記錄事件。"""
    payload = {
        "reason": reason,
        "items": items,
        "total_estimate": total_estimate,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id, wo_id=wo_id, tag="SCOPE_CHANGE", payload=payload
    )


async def record_material_request(
    *,
    tenant_id: str,
    wo_id: str,
    items: list[dict],
    urgency: str,
    note: str | None = None,
) -> dict:
    """記錄缺料回報（T6），等待調度員協調補料。"""
    payload = {"items": items, "urgency": urgency, "note": note}
    return await _append_subflow_event(
        tenant_id=tenant_id,
        wo_id=wo_id,
        tag="MATERIAL_REQUEST",
        payload=payload,
    )


async def record_delay(
    *,
    tenant_id: str,
    wo_id: str,
    delay_minutes: int,
    reason: str,
    reason_text: str | None = None,
    notify: str = "customer_only",
) -> dict:
    """記錄延遲通知（T7）。實際 LINE/SMS 推送由通知服務處理（此處僅留紀錄）。"""
    if delay_minutes < 5 or delay_minutes > 300:
        raise ApiError(
            "VALIDATION_ERROR",
            "delay_minutes must be between 5 and 300",
            422,
        )
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason,
        "reason_text": reason_text,
        "notify": notify,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id, wo_id=wo_id, tag="DELAY", payload=payload
    )


async def record_door_check(
    *,
    tenant_id: str,
    wo_id: str,
    checklist: dict,
    photos_before: list[str] | None = None,
    photos_after: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """記錄門面外觀檢核（T8）。photos 為媒體 URL 清單；MVP 僅記錄 placeholder 名稱。"""
    payload = {
        "checklist": checklist,
        "photos_before": photos_before or [],
        "photos_after": photos_after or [],
        "notes": notes,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id,
        wo_id=wo_id,
        tag="DOOR_CHECK",
        payload=payload,
    )


async def list_work_order_events(
    *,
    tenant_id: str,
    wo_id: str,
    event_type: str | None = None,
    limit: int = 100,
) -> dict:
    """列出某工單的事件（依時間倒序）。可依 event_type 過濾。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 先確認工單存在 + tenant 隔離
    await _fetch_status_for_update(wo_id, tenant_id)
    where = ["work_order_id = %s::uuid", "tenant_id = %s::uuid"]
    params: list = [wo_id, tenant_id]
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    params.append(limit)
    sql = (
        "SELECT id, event_type, payload, actor_user_id, created_at "
        "FROM work_order_events "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC LIMIT %s"
    )
    cur = await db_module._conn.execute(sql, tuple(params))
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "event_type": r[1],
            "payload": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {}),
            "actor_user_id": str(r[3]) if r[3] else None,
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        }
        for r in rows
    ]
    return {"items": items}


async def confirm_reschedule_by_customer(
    *,
    tenant_id: str,
    wo_id: str,
    selected_start: str,
    selected_end: str,
) -> dict:
    """客戶於 LINE Flex 選定改期時段 → 寫入 wo.scheduled_at + 紀錄事件 + 推 WS。

    對齊 Flow 11（v1.7.0 frontend 已監聽 reschedule_confirmed_by_customer 事件）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    try:
        start_dt = datetime.fromisoformat(selected_start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(selected_end.replace("Z", "+00:00"))
    except ValueError as e:
        raise ApiError(
            "VALIDATION_ERROR",
            "selected_start / selected_end 必須為 ISO 8601 格式",
            422,
        ) from e
    if end_dt <= start_dt:
        raise ApiError(
            "VALIDATION_ERROR",
            "selected_end must be after selected_start",
            422,
        )

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm reschedule in status '{current}'",
            409,
        )

    note = (
        f"[CUSTOMER_RESCHEDULE_CONFIRMED {_now_iso()}] "
        f"customer chose {start_dt.isoformat()}~{end_dt.isoformat()}"
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (start_dt, note, wo_id),
    )
    # 同時寫入結構化事件（v1.30.0 work_order_events）
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, 'reschedule_proposed', %s::jsonb)",
        (
            wo_id,
            tenant_id,
            json.dumps(
                {
                    "confirmed_by": "customer",
                    "selected_start": start_dt.isoformat(),
                    "selected_end": end_dt.isoformat(),
                },
                ensure_ascii=False,
            ),
        ),
    )

    # 推 WS — 前端 v1.13.0 監聽 reschedule_confirmed_by_customer
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": "reschedule_confirmed_by_customer",
                "payload": {
                    "event": "reschedule_confirmed_by_customer",
                    "work_order_id": wo_id,
                    "selected_start": start_dt.isoformat(),
                    "selected_end": end_dt.isoformat(),
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish reschedule_confirmed failed (non-fatal)")

    return await get_order(tenant_id=tenant_id, wo_id=wo_id)


async def reject_reschedule_by_customer(
    *, tenant_id: str, wo_id: str
) -> dict:
    """客戶 LINE Flex 點「都不方便」→ 推 WS 給技師端，wo 狀態不變。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 寫事件留下記錄
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, 'reschedule_proposed', %s::jsonb)",
        (
            wo_id,
            tenant_id,
            json.dumps({"rejected_by": "customer"}, ensure_ascii=False),
        ),
    )
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": "reschedule_rejected_by_customer",
                "payload": {
                    "event": "reschedule_rejected_by_customer",
                    "work_order_id": wo_id,
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish reschedule_rejected failed (non-fatal)")

    return await get_order(tenant_id=tenant_id, wo_id=wo_id)
