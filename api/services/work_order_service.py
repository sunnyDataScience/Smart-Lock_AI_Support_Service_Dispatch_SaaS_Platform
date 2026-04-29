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
