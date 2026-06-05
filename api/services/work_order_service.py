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


async def create_from_problem_card(
    *,
    tenant_id: str,
    pc_id: str,
    customer_address: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    created_by: str | None = None,
) -> tuple[dict, bool]:
    """從 confirmed ProblemCard 建立 WorkOrder（F-002 客服審 PC → 開 WO）。

    前置條件：PC.status = 'confirmed' 且未已存在對應 WO。
    Idempotency：同 PC 重複呼叫回既存 WO（created_flag=False，HTTP 200）；
    新建回 created_flag=True（HTTP 201）。

    customer_address / name / phone：優先用 caller 帶入；否則 fallback 到
    user 的 profile（users.address/display_name/phone）。address 兩者皆無 → 422。

    urgency / priority：PC.urgency 與 WO.priority 共用 DB enum
    (low/normal/high/urgent)，直接 pass-through。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 取 PC + 同 transaction lock 防止 race（兩個並發 convert 同一張 PC）
    cur = await db_module._conn.execute(
        "SELECT pc.status, pc.urgency, "
        "       u.address, u.display_name, u.phone "
        "FROM problem_cards pc "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND u.tenant_id = %s::uuid "
        "FOR UPDATE OF pc",
        (pc_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)

    pc_status, pc_urgency, user_address, user_name, user_phone = row

    if pc_status != "confirmed":
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot convert problem card in status '{pc_status}'; expected 'confirmed'",
            409,
        )

    # 2. Idempotency: existing WO with same problem_card_id?
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders "
        "WHERE problem_card_id = %s::uuid "
        "ORDER BY created_at ASC LIMIT 1",
        (pc_id,),
    )
    existing = await cur.fetchone()
    if existing:
        wo = await get_order(tenant_id=tenant_id, wo_id=str(existing[0]))
        return wo, False

    # 3. Resolve customer info（caller override > user profile fallback）
    final_address = customer_address or user_address
    if not final_address:
        raise ApiError(
            "VALIDATION_ERROR",
            "customer_address required: not found in user profile and not provided",
            422,
        )
    final_name = customer_name or user_name
    final_phone = customer_phone or user_phone
    # PC.urgency 與 WO.priority 共用 DB enum (low/normal/high/urgent)，直接 pass-through
    priority = pc_urgency or "normal"

    # 4. INSERT
    insert_cur = await db_module._conn.execute(
        "INSERT INTO work_orders "
        "  (problem_card_id, status, priority, "
        "   customer_name, customer_phone, customer_address, created_by) "
        "VALUES (%s::uuid, 'created', %s, %s, %s, %s, "
        "        %s::uuid) "
        "RETURNING id",
        (pc_id, priority, final_name, final_phone, final_address, created_by),
    )
    new_row = await insert_cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert work order", 500)
    new_wo_id = str(new_row[0])

    # 5. WS publish + return
    wo = await _publish_and_return(
        tenant_id=tenant_id, wo_id=new_wo_id, event_type="work_order.created"
    )
    return wo, True


_ACCEPT_FROM = {"assigned"}
_COMPLETE_FROM = {"accepted", "in_progress"}
_CANCEL_FROM = {"created", "assigned", "accepted", "in_progress"}
_ASSIGN_FROM = {"created", "assigned"}  # 允許重派（assigned → assigned 換人）
# Flow 8 二次派工：admin 強制改派可從 accepted / in_progress 收回（含 assigned，
# 與 assign_order 重疊但語意不同：reassign 明確記錄 old→new + dispatch_log action='reassign'）
_REASSIGN_FROM = {"assigned", "accepted", "in_progress"}
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


async def _publish_pool_change(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    event: str,  # "added" / "taken" / "cancelled"
) -> None:
    """推 `/realtime/pool/{technician_id}` event 對齊前端 pool/page.tsx 契約。

    前端 useRealtimeChannel 期待 payload:
      - added: 帶完整 work_order 物件（prepend 到列表）
      - taken: 帶 work_order_id（從列表移除）
      - cancelled: 帶 work_order_id（從列表移除）
    """
    if not technician_id:
        return
    try:
        from realtime.ws_hub import hub

        payload: dict = {"event": event, "work_order_id": wo_id}
        if event == "added":
            # added 需帶完整 wo 物件供 prepend
            try:
                payload["work_order"] = await get_order(
                    tenant_id=tenant_id, wo_id=wo_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("get_order failed for pool publish added")
        await hub.publish(
            f"/realtime/pool/{technician_id}",
            {
                "type": f"work_order.pool_{event}",
                "payload": payload,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "ws publish pool/%s event=%s failed (non-fatal)",
            technician_id[:8] if technician_id else "?", event,
        )


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
    # 取 technician_id 給 pool publish
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    tech_row = await cur.fetchone()
    tech_id = str(tech_row[0]) if tech_row and tech_row[0] else None
    await db_module._conn.execute(
        "UPDATE work_orders SET status = 'accepted', accepted_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (wo_id,),
    )
    # event=taken 從技師個人 pool 列表移除（已進 my-orders）
    if tech_id:
        await _publish_pool_change(
            tenant_id=tenant_id, wo_id=wo_id, technician_id=tech_id,
            event="taken",
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
    # 取 technician_id 給 pool publish (若已派)
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    tech_row = await cur.fetchone()
    tech_id = str(tech_row[0]) if tech_row and tech_row[0] else None
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
    # event=cancelled 把該 tech pool 該 wo 移除（若已派）
    if tech_id:
        await _publish_pool_change(
            tenant_id=tenant_id, wo_id=wo_id, technician_id=tech_id,
            event="cancelled",
        )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.cancelled"
    )


async def _detect_schedule_conflict_and_publish(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    window_hours: int = 2,
) -> None:
    """Flow 14 排班衝突偵測 — 同技師 ±window_hours 是否已有其他 active wo。

    偵測到衝突時：
      - INSERT work_order_events `event_type='schedule_conflict'`，
        payload 含 conflicting_wo_ids / technician_id / window_hours
      - WS publish 至 `/realtime/dispatch-queue`（admin 已訂閱）
        type='schedule_conflict_detected'

    不 raise — 衝突偵測為「軟訊號」，admin 可決定是否 reassign / reschedule；
    不阻擋既有 assign 路徑。失敗（DB / WS）也 swallow，避免影響主流。
    """
    if not await _ensure_conn():
        return
    try:
        cur = await db_module._conn.execute(
            "SELECT scheduled_at FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return
        scheduled_at = row[0]

        cur = await db_module._conn.execute(
            "SELECT id, scheduled_at FROM work_orders "
            "WHERE tenant_id = %s::uuid "
            "  AND technician_id = %s::uuid "
            "  AND id != %s::uuid "
            "  AND status NOT IN ('completed', 'confirmed', 'cancelled') "
            "  AND scheduled_at IS NOT NULL "
            "  AND scheduled_at BETWEEN "
            "      %s::timestamptz - (INTERVAL '1 hour' * %s) "
            "      AND %s::timestamptz + (INTERVAL '1 hour' * %s)",
            (tenant_id, technician_id, wo_id,
             scheduled_at, window_hours, scheduled_at, window_hours),
        )
        rows = await cur.fetchall()
        if not rows:
            return

        conflicting_ids = [str(r[0]) for r in rows]
        payload = {
            "conflicting_wo_ids": conflicting_ids,
            "technician_id": str(technician_id),
            "window_hours": window_hours,
            "scheduled_at": scheduled_at.isoformat() if hasattr(scheduled_at, "isoformat") else str(scheduled_at),
        }
        await db_module._conn.execute(
            "INSERT INTO work_order_events "
            "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
            "VALUES (%s::uuid, %s::uuid, NULL, 'schedule_conflict', %s::jsonb)",
            (wo_id, tenant_id, json.dumps(payload, ensure_ascii=False)),
        )
        try:
            from realtime.ws_hub import hub
            await hub.publish(
                "/realtime/dispatch-queue",
                {
                    "type": "schedule_conflict_detected",
                    "payload": {
                        "work_order_id": str(wo_id),
                        **payload,
                    },
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("ws publish schedule_conflict failed (non-fatal)")
        # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker render conflict
        # 通知 admin 或客戶；補救流由業主 admin 決定走 reassign/reschedule)。
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="schedule_conflict",
                payload=payload,
                reference_id=str(wo_id),
                reference_table="work_orders",
            )
        except Exception:  # noqa: BLE001
            logger.exception("outbox enqueue schedule_conflict failed (non-fatal)")
    except Exception:  # noqa: BLE001
        logger.exception("schedule conflict detection failed (non-fatal)")


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
    # Flow 14 排班衝突軟偵測（best-effort，不阻擋 assign）
    await _detect_schedule_conflict_and_publish(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=technician_id,
    )
    # /realtime/pool/{tech_id} publish — 對齊前端 pool/page.tsx 契約
    # event=added 帶完整 wo 物件 → 前端列表 prepend
    await _publish_pool_change(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=technician_id,
        event="added",
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.assigned"
    )


async def reassign_order(
    *,
    tenant_id: str,
    wo_id: str,
    new_technician_id: str,
    reason: str,
    actor_user_id: str | None = None,
) -> dict:
    """Flow 8 二次派工 — admin 強制改派（不破壞 wo_id / events / customer history）。

    與 assign_order 差異：
      - 接受 _REASSIGN_FROM = {assigned, accepted, in_progress}（涵蓋 accepted/
        in_progress，後兩者 assign_order 拒絕）
      - 強制收回後 status 回到 'assigned'（即使原本 accepted/in_progress）
      - 寫 dispatch_logs.action='reassign' 留 audit 軌跡
      - 422 NO_OP_SAME_TECHNICIAN 若新舊技師相同

    使用情境：
      - admin 發現指派錯誤但工單已 accepted
      - 客戶要求換技師
      - 原技師臨時無法執行（病假 / 排程衝突）但 wo 已開始
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _REASSIGN_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reassign work order in status '{current}'; "
            f"expected one of {sorted(_REASSIGN_FROM)}",
            409,
        )

    # 取得原技師
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    old_technician_id = str(row[0]) if row and row[0] else None
    if old_technician_id == str(new_technician_id):
        raise ApiError(
            "NO_OP_SAME_TECHNICIAN",
            "new_technician_id is the same as current technician",
            422,
        )

    # 驗新技師同 tenant + active
    cur = await db_module._conn.execute(
        "SELECT id, status FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (new_technician_id, tenant_id),
    )
    tech_row = await cur.fetchone()
    if not tech_row:
        raise ApiError(
            "TECHNICIAN_NOT_FOUND",
            "new technician not found in this tenant",
            404,
        )
    if tech_row[1] != "active":
        raise ApiError(
            "TECHNICIAN_NOT_AVAILABLE",
            f"new technician status is '{tech_row[1]}'; only 'active' can be reassigned",
            409,
        )

    note = f"[REASSIGN] {old_technician_id or 'unassigned'} → {new_technician_id}: {reason}"
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  technician_id = %s::uuid, "
        "  status = 'assigned', "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_technician_id, note, wo_id),
    )
    # dispatch_logs audit（schema: 無 tenant_id；隔離靠 join）
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs "
        "  (work_order_id, action, technician_id, notes) "
        "VALUES (%s::uuid, 'reassign', %s::uuid, %s)",
        (wo_id, new_technician_id, reason),
    )
    # 也寫一筆 work_order_events 對齊 subflow timeline 觀感
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, %s, 'reassign', %s::jsonb)",
        (
            wo_id,
            tenant_id,
            actor_user_id,
            json.dumps(
                {
                    "old_technician_id": old_technician_id,
                    "new_technician_id": str(new_technician_id),
                    "reason": reason,
                    "from_status": current,
                },
                ensure_ascii=False,
            ),
        ),
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.reassigned"
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
    actor_user_id: str | None = None,
) -> dict:
    """記錄範圍變更申請（T5；Flow 3）。

    2026-06-05 補完 proposal INSERT 鏈路（之前淺取證腦補 90% 過高，deep audit 校正 65% — `scope_changes` 表 schema 存在但
    0 caller、token mint 機制存在但無 caller）：

      1. 從 wo 取 technician_id（_SUBFLOW_FROM 保證非 NULL）+ estimated_price
      2. INSERT scope_changes 表（status='pending'）
      3. mint public_token (purpose='scope_change', ttl_days=7)
      4. 仍寫 work_order_events SCOPE_CHANGE tag（保留 subflow timeline 觀感）
      5. _publish_and_return 推 WS

    回傳 envelope 加入 `scope_change_id` + `public_token`，caller（admin /
    技師 UI / 後續 LINE Flex push 模組）可拿 token 自行決定通知方式。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record SCOPE_CHANGE in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )

    # 取 wo 的 technician_id + estimated_price 作 scope_changes 必填欄位
    cur = await db_module._conn.execute(
        "SELECT technician_id, estimated_price FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    if not row or not row[0]:
        # _SUBFLOW_FROM 理應保證 technician_id 非 NULL，但安全防呆
        raise ApiError(
            "VALIDATION_ERROR",
            "work order has no technician_id; cannot record scope change",
            422,
        )
    technician_id = str(row[0])
    original_price = float(row[1]) if row[1] is not None else 0.0
    try:
        new_price = float(total_estimate) if total_estimate else None
    except (TypeError, ValueError):
        new_price = None

    # INSERT scope_changes 表
    cur = await db_module._conn.execute(
        "INSERT INTO scope_changes "
        "  (work_order_id, technician_id, reason, "
        "   original_scope, new_scope, original_price, new_price, status) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s, 'pending') "
        "RETURNING id",
        (
            wo_id,
            technician_id,
            reason,
            # original_scope MVP 留簡化標記；future 可從 problem_card 摘要填
            json.dumps({"snapshot": "from_work_order", "estimated_price": original_price}, ensure_ascii=False),
            json.dumps({"items": items, "total_estimate": total_estimate}, ensure_ascii=False),
            original_price,
            new_price,
        ),
    )
    new_row = await cur.fetchone()
    scope_change_id = str(new_row[0])

    # mint public_token（caller 可給 customer LINE Flex / web link）
    # 延遲 import 避 circular 並讓本 service 不強依賴 token 模組
    try:
        from services import public_token
        token = public_token.generate_token(
            scope_change_id,
            purpose="scope_change",
            ttl_days=7,
            tenant_id=tenant_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("public_token mint failed (non-fatal); returning no token")
        token = None

    # 仍寫 work_order_events 保 subflow timeline
    payload = {
        "reason": reason,
        "items": items,
        "total_estimate": total_estimate,
        "scope_change_id": scope_change_id,
    }
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, %s, 'scope_change', %s::jsonb)",
        (wo_id, tenant_id, actor_user_id, json.dumps(payload, ensure_ascii=False)),
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )

    # token mint log（admin 可從 scope_changes table 查詢；token 由 outbox
    # payload 帶給 worker render Flex 用）
    if token:
        logger.info(
            "scope_change_id=%s token minted (ttl_days=7)",
            scope_change_id,
        )

    # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker render scope_change
    # proposal Flex 含 accept/reject 按鈕 + token 連結)。best-effort 不阻擋主流。
    try:
        from services import line_push_outbox_service
        await line_push_outbox_service.enqueue(
            tenant_id=tenant_id,
            push_kind="scope_change_proposal",
            payload={
                "scope_change_id": scope_change_id,
                "work_order_id": wo_id,
                "reason": reason,
                "items": items,
                "total_estimate": total_estimate,
                "public_token": token,
            },
            reference_id=scope_change_id,
            reference_table="scope_changes",
        )
    except Exception:  # noqa: BLE001
        logger.exception("outbox enqueue scope_change_proposal failed (non-fatal)")

    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.subflow.scope_change"
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


async def mark_material_request_supplied(
    *,
    tenant_id: str,
    wo_id: str,
    material_request_event_id: str,
    supplied_by_user_id: str,
    note: str | None = None,
) -> dict:
    """admin 標記某筆 material_request 已補料完成（Flow 4 收尾）。

    寫 event_type='supply_arrived' 事件，payload 含 material_request_event_id
    指回原回報事件（join 關係）；list_pending_material_requests 以此過濾掉
    已收尾的回報。

    驗證：
      - material_request_event_id 必須存在且同 tenant 且 event_type='material_request'
        且屬於該 wo（防 admin 誤標他單）
      - 同 material_request 不可重複 supplied（DUP_SUPPLY 409）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 確認 wo 存在 + tenant 隔離
    await _fetch_status_for_update(wo_id, tenant_id)
    # 驗 material_request_event
    cur = await db_module._conn.execute(
        "SELECT event_type, work_order_id FROM work_order_events "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (material_request_event_id, tenant_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise ApiError(
            "EVENT_NOT_FOUND",
            "material_request_event_id not found in this tenant",
            404,
        )
    if row[0] != "material_request":
        raise ApiError(
            "INVALID_EVENT_TYPE",
            f"event {material_request_event_id} is '{row[0]}', expected 'material_request'",
            422,
        )
    if str(row[1]) != str(wo_id):
        raise ApiError(
            "EVENT_WO_MISMATCH",
            "material_request event does not belong to this work order",
            422,
        )
    # 防重複 supplied
    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_order_events "
        "WHERE tenant_id = %s::uuid "
        "  AND event_type = 'supply_arrived' "
        "  AND (payload->>'material_request_event_id')::uuid = %s::uuid "
        "LIMIT 1",
        (tenant_id, material_request_event_id),
    )
    if await cur.fetchone() is not None:
        raise ApiError(
            "DUP_SUPPLY",
            "this material_request has already been marked supplied",
            409,
        )
    # INSERT supply_arrived event
    payload = {
        "material_request_event_id": material_request_event_id,
        "note": note,
    }
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)",
        (
            wo_id,
            tenant_id,
            supplied_by_user_id,
            "supply_arrived",
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )
    return await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type="work_order.subflow.supply_arrived",
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


async def submit_door_check_v2(
    *,
    tenant_id: str,
    wo_id: str,
    checklist: dict,
    photos_before: list[str] | None = None,
    photos_after: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """CR-0007 HD-01=(a)：door-check 強制 arrival 前置。

    流程：
      1. 查 work_order_events WHERE event_type='arrival'，不存在 → 409
      2. 呼叫 record_door_check（沿用既有路徑，HD-05=freeform 不另驗）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # tenant + work_order 存在性檢查（順帶確認 tenant scope）
    await _fetch_status_for_update(wo_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_order_events "
        "WHERE work_order_id = %s::uuid "
        "  AND tenant_id = %s::uuid "
        "  AND event_type = 'arrival' "
        "LIMIT 1",
        (wo_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError(
            "STATE_CONFLICT",
            "door-check requires prior arrival event (CR-0007 HD-01)",
            409,
        )

    return await record_door_check(
        tenant_id=tenant_id,
        wo_id=wo_id,
        checklist=checklist,
        photos_before=photos_before,
        photos_after=photos_after,
        notes=notes,
    )


async def propose_reschedule_v2(
    *,
    tenant_id: str,
    wo_id: str,
    proposed_slots: list[dict],
    message_to_customer: str | None,
    send_via: str,
    proposed_by_user_id: str,
    proposed_by_role: str,
) -> dict:
    """CR-0007 多時段改約提案 v2（寫 saas.reschedule_proposal 獨立表 HD-04=a）。

    HD-02=(a) slots 1-3（DB CHECK 兜底，service 層先驗）
    HD-03=(a) sla_deadline DEFAULT NOW + 24h
    """
    if not isinstance(proposed_slots, list) or not (1 <= len(proposed_slots) <= 3):
        raise ApiError(
            "VALIDATION_ERROR",
            "proposed_slots must be a list of 1-3 items (CR-0007 HD-02)",
            422,
        )
    if send_via not in {"line", "sms", "email"}:
        raise ApiError("VALIDATION_ERROR", "send_via must be line|sms|email", 422)
    if proposed_by_role not in {"technician", "operations_manager", "admin"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "proposed_by_role must be technician|operations_manager|admin",
            422,
        )
    if message_to_customer and len(message_to_customer) > 500:
        raise ApiError("VALIDATION_ERROR", "message_to_customer max 500 chars", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 確認工單存在 + tenant scope（藉用既有狀態查詢）
    await _fetch_status_for_update(wo_id, tenant_id)

    cur = await db_module._conn.execute(
        "INSERT INTO saas.reschedule_proposal "
        "  (work_order_id, tenant_id, proposed_slots, message_to_customer, "
        "   send_via, proposed_by_user_id, proposed_by_role) "
        "VALUES (%s::uuid, %s::uuid, %s::jsonb, %s, %s, %s::uuid, %s) "
        "RETURNING id, status, sla_deadline, created_at",
        (
            wo_id,
            tenant_id,
            json.dumps(proposed_slots, ensure_ascii=False),
            message_to_customer,
            send_via,
            proposed_by_user_id,
            proposed_by_role,
        ),
    )
    row = await cur.fetchone()
    proposal_id = str(row[0])

    # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker 將 render reschedule
    # carousel + push 客戶 LINE)。best-effort 不阻擋主流；send_via='line' 才推。
    if send_via == "line":
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="reschedule_proposal",
                payload={
                    "proposal_id": proposal_id,
                    "work_order_id": wo_id,
                    "proposed_slots": proposed_slots,
                    "message_to_customer": message_to_customer,
                },
                reference_id=proposal_id,
                reference_table="saas.reschedule_proposal",
            )
        except Exception:  # noqa: BLE001
            logger.exception("outbox enqueue reschedule_proposal failed (non-fatal)")

    return {
        "id": proposal_id,
        "work_order_id": wo_id,
        "status": row[1],
        "sla_deadline": row[2].isoformat() if row[2] else None,
        "created_at": row[3].isoformat() if row[3] else None,
        "proposed_slots": proposed_slots,
        "send_via": send_via,
    }


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


async def list_pending_material_requests(
    *,
    tenant_id: str,
    limit: int = 100,
) -> dict:
    """跨工單列出近期的缺料回報（Flow 4 admin 補料管理彙整視圖）。

    每 row 為一筆 material_request 事件 + 對應工單上下文：
      - event_id / created_at / payload (items[], urgency, note)
      - work_order_id / wo_status / scheduled_at / technician_id

    排序：urgency 急迫度（now > today > tomorrow）→ created_at DESC。
    MVP 不分 pending vs supplied（後者需新 event_type 'supply_arrived'
    機制，本 commit OOSCope）；本 endpoint 提供「最近活躍的缺料事件」清單，
    admin 進入工單詳情頁進一步處理。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    # LEFT JOIN supply_arrived events 過濾掉已收尾的 material_request（後者
    # 透過 payload->>'material_request_event_id' 指回原 material_request.id）。
    sql = (
        "SELECT "
        "  e.id, e.created_at, e.payload, e.actor_user_id, "
        "  e.work_order_id, wo.status, wo.scheduled_at, wo.technician_id "
        "FROM work_order_events e "
        "JOIN work_orders wo ON e.work_order_id = wo.id "
        "LEFT JOIN work_order_events sa "
        "  ON sa.tenant_id = e.tenant_id "
        "  AND sa.event_type = 'supply_arrived' "
        "  AND (sa.payload->>'material_request_event_id')::uuid = e.id "
        "WHERE e.tenant_id = %s::uuid "
        "  AND e.event_type = 'material_request' "
        "  AND wo.status NOT IN ('completed', 'confirmed', 'cancelled') "
        "  AND sa.id IS NULL "
        "ORDER BY "
        # urgency 優先：now=0 / today=1 / tomorrow=2 / 其他=9
        "  CASE COALESCE(e.payload->>'urgency', '') "
        "    WHEN 'now' THEN 0 "
        "    WHEN 'today' THEN 1 "
        "    WHEN 'tomorrow' THEN 2 "
        "    ELSE 9 END, "
        "  e.created_at DESC "
        "LIMIT %s"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, limit))
    rows = await cur.fetchall()

    items = [
        {
            "event_id": str(r[0]),
            "created_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
            "payload": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {}),
            "actor_user_id": str(r[3]) if r[3] else None,
            "work_order_id": str(r[4]),
            "wo_status": r[5],
            "scheduled_at": r[6].isoformat() if hasattr(r[6], "isoformat") else None,
            "technician_id": str(r[7]) if r[7] else None,
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


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


# =============================================================================
# Public anonymous endpoint helper — Q3=C
# =============================================================================
#
# 不帶 tenant gate；呼叫者必須先用 token 解出 work_order_id 才能進來。
# 完工 90 天封存：completed_at < NOW() - 90d 時 raise 410。
# 回傳僅供 PII 遮罩後的展示欄位，不含金額 / 客戶完整地址。


# customer-facing 狀態映射：把內部狀態收斂成消費者能理解的 6 種
_PUBLIC_STATUS_MAP = {
    "created": "pending",
    "assigned": "scheduled",
    "accepted": "scheduled",
    "on_the_way": "on_the_way",
    "in_progress": "in_progress",
    "completed": "completed",
    "confirmed": "completed",
    "cancelled": "cancelled",
}


# =============================================================================
# F-010 Reschedule / Delay quick-action ops（含 LINE Push 真實串接）
# =============================================================================
#
# 與既有的 propose_reschedule (Flow 11 LINE Flex RSVP) / record_delay (T7 事件)
# 互補：
#   - request_reschedule  ：技師 / admin 直接改 scheduled_at，不走 RSVP（單方變更）
#   - approve_reschedule  ：admin 對 request_reschedule 提案做核准 / 退回
#   - notify_delay        ：在 record_delay 之後，主動 LINE push 通知客戶
#
# 三個動作完成後一律寫 audit_event + 嘗試 LINE push（fail-soft）。
#
# Reschedule request lifecycle（state in service_report tag）：
#   [RESCHEDULE_REQUEST@<iso> by=<uid> from=<old_iso> to=<new_iso> reason=<text>]
#   [RESCHEDULE_DECISION@<iso> by=<uid> decision=approve|reject comment=<text>]


_RESCHEDULE_REASON_MAX = 500


async def _audit_action(
    *,
    action: str,
    actor_id: str | None,
    actor_role: str | None,
    work_order_id: str,
    payload: dict,
) -> None:
    """Best-effort audit write — must not fail caller."""
    try:
        from services import audit_log_service

        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            target_type="work_order",
            target_id=work_order_id,
            payload=payload,
        )
    except Exception:  # noqa: BLE001
        logger.warning("audit %s failed", action, exc_info=True)


async def request_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    new_scheduled_at: str,
    reason: str,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Technician / admin requests an immediate reschedule.

    - 技師只能改自己的工單；admin 不限。
    - 不寫 RSVP，直接更新 scheduled_at 並 LINE push 通知客戶（fail-soft）。
    - 回傳：{"work_order": ..., "notification_sent": bool, "channel": "line"|"none",
              "new_scheduled_at": iso}
    """
    # ─── validation ───────────────────────────────────────────────────────
    if not new_scheduled_at:
        raise ApiError("VALIDATION_ERROR", "new_scheduled_at is required", 422)
    try:
        from datetime import datetime as _dt2, timezone as _tz

        new_dt = _dt2.fromisoformat(new_scheduled_at.replace("Z", "+00:00"))
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=_tz.utc)
    except ValueError as e:
        raise ApiError("VALIDATION_ERROR", "new_scheduled_at must be ISO 8601", 422) from e
    if new_dt <= _dt2.now(_tz.utc):
        raise ApiError(
            "VALIDATION_ERROR",
            "new_scheduled_at must be in the future",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)
    if len(reason) > _RESCHEDULE_REASON_MAX:
        raise ApiError(
            "VALIDATION_ERROR",
            f"reason must be at most {_RESCHEDULE_REASON_MAX} chars",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # ─── tenant + ownership check ─────────────────────────────────────────
    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.technician_id, wo.scheduled_at {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, tech_id, old_scheduled = row[0], row[1], row[2]

    if current_status not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reschedule in status '{current_status}'; "
            f"expected one of {sorted(_RESCHEDULE_FROM)}",
            409,
        )

    # 技師 RBAC：只能改自己被指派的工單
    if actor_role == "technician":
        if tech_id is None or str(tech_id) != actor_user_id:
            raise ApiError(
                "FORBIDDEN",
                "Technicians can only reschedule their own work orders",
                403,
            )

    # ─── apply ────────────────────────────────────────────────────────────
    from datetime import datetime as _dt2, timezone as _tz

    now_iso = _dt2.now(_tz.utc).isoformat()
    note = (
        f"[RESCHEDULE_REQUEST@{now_iso}] by={actor_user_id} "
        f"from={old_scheduled.isoformat() if old_scheduled else 'unset'} "
        f"to={new_dt.isoformat()} reason={reason.strip()[:_RESCHEDULE_REASON_MAX]}"
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_dt, note, wo_id),
    )

    # ─── audit + LINE push ────────────────────────────────────────────────
    await _audit_action(
        action="work_order.reschedule_requested",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload={
            "new_scheduled_at": new_dt.isoformat(),
            "old_scheduled_at": old_scheduled.isoformat() if old_scheduled else None,
            "reason": reason.strip()[:_RESCHEDULE_REASON_MAX],
        },
    )

    from services import line_push_service

    text = (
        f"您的工單 #{wo_id[:8]} 已改約至 "
        f"{new_dt.strftime('%Y-%m-%d %H:%M')}（原因：{reason.strip()[:50]}）"
    )
    notification_sent, channel = await line_push_service.push_to_work_order_customer(
        tenant_id=tenant_id,
        work_order_id=wo_id,
        text=text,
        actor_user_id=actor_user_id,
    )

    order = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.reschedule_requested"
    )
    return {
        "work_order": order,
        "rescheduled": True,
        "new_scheduled_at": new_dt.isoformat(),
        "notification_sent": notification_sent,
        "channel": channel,
    }


async def approve_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    decision: str,
    comment: str | None,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Admin / operations_manager approves or rejects a reschedule request.

    decision='approve' → 不修改 scheduled_at（已在 request 時更新），僅蓋審核章
    decision='reject' → 復原 scheduled_at 至最近一次 [RESCHEDULE_REQUEST] 之 `from`
    """
    if decision not in {"approve", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'approve' or 'reject'", 422)
    if comment and len(comment) > _RESCHEDULE_REASON_MAX:
        raise ApiError(
            "VALIDATION_ERROR",
            f"comment must be at most {_RESCHEDULE_REASON_MAX} chars",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.service_report, wo.scheduled_at {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, report_text = row[0], (row[1] or "")

    if current_status not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot approve/reject reschedule in status '{current_status}'",
            409,
        )

    from datetime import datetime as _dt2, timezone as _tz

    now_iso = _dt2.now(_tz.utc).isoformat()

    # 'reject' → 嘗試從最近一筆 [RESCHEDULE_REQUEST] 還原 from
    revert_to: _dt2 | None = None
    if decision == "reject":
        for line in reversed(report_text.splitlines()):
            if "[RESCHEDULE_REQUEST@" not in line or "from=" not in line:
                continue
            # parse "from=<iso>" segment
            try:
                from_seg = line.split("from=", 1)[1].split(" ", 1)[0]
                if from_seg == "unset":
                    break
                revert_to = _dt2.fromisoformat(from_seg.replace("Z", "+00:00"))
                if revert_to.tzinfo is None:
                    revert_to = revert_to.replace(tzinfo=_tz.utc)
                break
            except (ValueError, IndexError):
                continue

    note = (
        f"[RESCHEDULE_DECISION@{now_iso}] by={actor_user_id} "
        f"decision={decision}"
    )
    if comment:
        note += f" comment={comment.strip()[:_RESCHEDULE_REASON_MAX]}"

    if decision == "reject" and revert_to is not None:
        await db_module._conn.execute(
            "UPDATE work_orders SET "
            "  scheduled_at = %s::timestamptz, "
            "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid",
            (revert_to, note, wo_id),
        )
    else:
        await db_module._conn.execute(
            "UPDATE work_orders SET "
            "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid",
            (note, wo_id),
        )

    await _audit_action(
        action=f"work_order.reschedule_{decision}d",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload={
            "decision": decision,
            "comment": (comment or "").strip()[:_RESCHEDULE_REASON_MAX] or None,
            "reverted_to": revert_to.isoformat() if revert_to else None,
        },
    )

    order = await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type=f"work_order.reschedule_{decision}d",
    )
    return {
        "work_order": order,
        "decision": decision,
        "reverted": revert_to is not None,
    }


async def notify_delay(
    *,
    tenant_id: str,
    wo_id: str,
    delay_minutes: int,
    reason: str,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Technician notifies customer of an in-flight delay (LINE push)。

    記錄事件（同 record_delay）+ LINE push（Q8=A V1.0 only LINE）。
    """
    if not isinstance(delay_minutes, int) or delay_minutes < 5 or delay_minutes > 300:
        raise ApiError(
            "VALIDATION_ERROR",
            "delay_minutes must be an integer between 5 and 300",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)
    if len(reason) > 500:
        raise ApiError("VALIDATION_ERROR", "reason must be at most 500 chars", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # tenant + ownership check
    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.technician_id {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, tech_id = row[0], row[1]
    if current_status not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot notify delay in status '{current_status}'; "
            f"expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    if actor_role == "technician":
        if tech_id is None or str(tech_id) != actor_user_id:
            raise ApiError(
                "FORBIDDEN",
                "Technicians can only notify delays for their own work orders",
                403,
            )

    # 寫結構化事件（重用 _append_subflow_event 但避免重複狀態檢查 — 直接 INSERT）
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason.strip()[:500],
        "channel_attempt": "line",
    }
    await db_module._conn.execute(
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload) "
        "VALUES (%s::uuid, %s::uuid, %s, 'delay', %s::jsonb)",
        (wo_id, tenant_id, actor_user_id, json.dumps(payload, ensure_ascii=False)),
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )

    await _audit_action(
        action="work_order.delay_notified",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload=payload,
    )

    from services import line_push_service

    text = (
        f"您的工單 #{wo_id[:8]} 將延遲約 {delay_minutes} 分鐘抵達，"
        f"造成不便敬請見諒（原因：{reason.strip()[:50]}）"
    )
    notification_sent, channel = await line_push_service.push_to_work_order_customer(
        tenant_id=tenant_id,
        work_order_id=wo_id,
        text=text,
        actor_user_id=actor_user_id,
    )

    order = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.delay_notified"
    )
    return {
        "work_order": order,
        "notification_sent": notification_sent,
        "channel": channel,
    }


async def get_public_status(*, work_order_id: str) -> dict | None:
    """讀取工單對外可揭露的狀態欄位。

    回傳 dict（含未遮罩的技師欄位，由 router 套 mask）；查無資料回 None；
    超過 90 天封存則 raise ApiError(410)。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        "SELECT wo.id, wo.status, wo.scheduled_at, wo.completed_at, "
        "       t.name, t.phone "
        "FROM work_orders wo "
        "LEFT JOIN technicians t ON wo.technician_id = t.id "
        "WHERE wo.id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (work_order_id,))
    row = await cur.fetchone()
    if not row:
        return None

    completed_at = row[3]
    if completed_at is not None:
        from datetime import datetime, timedelta, timezone

        archive_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        if completed_at < archive_cutoff:
            raise ApiError("GONE", "工單完工超過 90 天，連結已封存", 410)

    return {
        "work_order_id": str(row[0]),
        "raw_status": row[1],
        "public_status": _PUBLIC_STATUS_MAP.get(row[1], "pending"),
        "scheduled_at": row[2].isoformat() if row[2] else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "technician_name": row[4],
        "technician_phone": row[5],
    }


# ============================================================
# CR-0017 Stage 4 — postback-driven 改約決議 wrapper
# ============================================================

async def confirm_reschedule_by_proposal(
    *, proposal_id: str, slot_idx: int
) -> dict:
    """LINE postback 觸發：依 proposal_id + slot_idx 反查 → confirm reschedule。

    1. SELECT proposed_slots, work_order_id, tenant_id, status FROM saas.reschedule_proposal
    2. 驗 status='pending' + slot_idx 在範圍內
    3. 呼 confirm_reschedule_by_customer 寫 work_orders
    4. UPDATE saas.reschedule_proposal SET chosen_slot_index, customer_responded_at,
       status='customer_confirmed'

    Raises:
        ApiError(404): proposal 不存在
        ApiError(409): proposal 已決議
        ApiError(422): slot_idx 越界
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT work_order_id, tenant_id, proposed_slots, status "
        "FROM saas.reschedule_proposal WHERE id = %s::uuid",
        (proposal_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "reschedule proposal not found", 404)
    wo_id = str(row[0])
    tenant_id = str(row[1])
    proposed_slots = row[2] if isinstance(row[2], list) else json.loads(row[2] or "[]")
    current_status = row[3]
    if current_status != "pending":
        raise ApiError(
            "CONFLICT", f"proposal already decided: {current_status}", 409,
        )
    if slot_idx < 0 or slot_idx >= len(proposed_slots):
        raise ApiError("VALIDATION_ERROR", "slot_idx out of range", 422)

    slot = proposed_slots[slot_idx]
    selected_start = slot.get("start")
    selected_end = slot.get("end") or selected_start
    if not selected_start:
        raise ApiError("VALIDATION_ERROR", "proposed slot missing 'start'", 422)

    # 1. 寫 work_orders（既有 service）
    result = await confirm_reschedule_by_customer(
        tenant_id=tenant_id,
        wo_id=wo_id,
        selected_start=selected_start,
        selected_end=selected_end,
    )

    # 2. CAS update saas.reschedule_proposal
    upd = await db_module._conn.execute(
        "UPDATE saas.reschedule_proposal SET "
        "  status = 'customer_confirmed', "
        "  chosen_slot_index = %s, "
        "  customer_responded_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending' "
        "RETURNING id",
        (slot_idx, proposal_id),
    )
    if not await upd.fetchone():
        # race 不阻斷主流程（work_orders 已寫）
        logger.warning(
            "reschedule_proposal CAS race: id=%s already decided after wo update",
            proposal_id,
        )
    return result


async def reject_reschedule_by_proposal(*, proposal_id: str) -> dict:
    """LINE postback「都不方便」→ reject reschedule + 寫 reschedule_proposal。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT work_order_id, tenant_id, status "
        "FROM saas.reschedule_proposal WHERE id = %s::uuid",
        (proposal_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "reschedule proposal not found", 404)
    wo_id = str(row[0])
    tenant_id = str(row[1])
    if row[2] != "pending":
        raise ApiError("CONFLICT", f"proposal already decided: {row[2]}", 409)

    result = await reject_reschedule_by_customer(tenant_id=tenant_id, wo_id=wo_id)
    await db_module._conn.execute(
        "UPDATE saas.reschedule_proposal SET "
        "  status = 'customer_rejected', "
        "  customer_responded_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending'",
        (proposal_id,),
    )
    return result
