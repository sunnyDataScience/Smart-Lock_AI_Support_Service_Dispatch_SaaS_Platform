"""OHS 現場報價修正 command(WBS 2.4.3/CR-0144/ADR-027)。

技師平台只發 command(diff 草稿不含金額),品牌報價引擎為唯一權威:
command 驗證(assignee/工單狀態)→ 冪等記錄 → 建 quote v+1(supersedes 串鏈,
draft 進既有 CR-0128 審核流,金額由小編定價)→ audit。
"""

from __future__ import annotations

import json
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service, quote_engine_service

logger = logging.getLogger("api.requote_service")

_REASONS = {"estimate_error", "scope_add", "scope_change"}
# 工單狀態機無 on_site(ADR-027 語彙)——現場作業對映 in_progress
_ALLOWED_WO_STATUS = {"in_progress"}


def _row_to_dict(row: tuple) -> dict:
    return {
        "request_id": row[0], "work_order_id": str(row[1]),
        "technician_id": str(row[2]), "reason": row[3],
        "initiated_via": row[4], "status": row[5],
        "created_quote_id": str(row[6]) if row[6] else None,
    }


_SELECT = ("request_id, work_order_id, technician_id, reason, "
           "initiated_via, status, created_quote_id")


async def submit_requote(
    *, request_id: str, work_order_id: str, technician_id: str,
    reason: str, item_diffs: list, initiated_via: str = "technician_command",
    tenant_id: str | None = None,
) -> tuple[dict, bool]:
    """回 (result, replayed)。冪等:同 request_id 回放既有結果。"""
    if reason not in _REASONS:
        raise ApiError("VALIDATION_ERROR", f"reason 須為 {sorted(_REASONS)}", 422)
    if initiated_via not in ("technician_command", "cs_fallback"):
        raise ApiError("VALIDATION_ERROR", "initiated_via 不合法", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    tenant = tenant_id or os.environ.get(
        "AGENT_TENANT_ID", "00000000-0000-0000-0000-000000000001")

    # 冪等回放
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM requote_requests "
        "WHERE tenant_id=%s::uuid AND request_id=%s", (tenant, request_id))
    row = await cur.fetchone()
    if row:
        return _row_to_dict(row), True

    # 工單驗證:存在/assignee/狀態
    cur = await db_module._conn.execute(
        "SELECT technician_id, status FROM work_orders WHERE id=%s::uuid",
        (work_order_id,))
    wo = await cur.fetchone()
    if not wo:
        raise ApiError("NOT_FOUND", "work order not found", 404)
    wo_tech, wo_status = (str(wo[0]) if wo[0] else None), wo[1]
    if not wo_tech or wo_tech != technician_id:
        raise ApiError("FORBIDDEN", "technician 非本工單 assignee(ADR-027)", 403)
    if wo_status not in _ALLOWED_WO_STATUS:
        raise ApiError("FORBIDDEN",
                       f"工單狀態 {wo_status} 不可發起現場修正(須 in_progress)", 403)

    # 同工單進行中修正 → 409(冪等衝突)
    cur = await db_module._conn.execute(
        "SELECT request_id FROM requote_requests "
        "WHERE work_order_id=%s::uuid AND status IN ('received','quoted')",
        (work_order_id,))
    if await cur.fetchone():
        raise ApiError("STATE_CONFLICT", "已有進行中的修正請求", 409)

    # 找現行最新版報價(supersedes 串鏈上一環)
    cur = await db_module._conn.execute(
        "SELECT id FROM quote WHERE work_order_id=%s::uuid "
        "ORDER BY version DESC LIMIT 1", (work_order_id,))
    prev = await cur.fetchone()
    prev_quote_id = str(prev[0]) if prev else None

    # 品牌報價引擎建 v+1 draft(金額由小編後續定價——技師零定價權)。
    # created_by FK 指向 users:由 technicians.user_id 反查(technician_id 是技師主檔 id)
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id=%s::uuid", (technician_id,))
    urow = await cur.fetchone()
    quote = await quote_engine_service.create_quote(
        tenant_id=tenant, work_order_id=work_order_id,
        created_by=str(urow[0]) if urow and urow[0] else None)
    new_quote_id = str(quote["id"])
    if prev_quote_id:
        await db_module._conn.execute(
            "UPDATE quote SET supersedes_quote_id=%s::uuid WHERE id=%s::uuid",
            (prev_quote_id, new_quote_id))

    cur = await db_module._conn.execute(
        "INSERT INTO requote_requests "
        " (tenant_id, request_id, work_order_id, technician_id, reason, "
        "  item_diffs, initiated_via, status, created_quote_id) "
        "VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s, %s::jsonb, %s, 'quoted', %s::uuid) "
        f"RETURNING {_SELECT}",
        (tenant, request_id, work_order_id, technician_id, reason,
         json.dumps(item_diffs, ensure_ascii=False), initiated_via, new_quote_id))
    out = _row_to_dict(await cur.fetchone())
    out["quote_version"] = quote.get("version")
    out["supersedes_quote_id"] = prev_quote_id

    try:
        await audit_log_service.log_event(
            event_type="quote", actor_id=technician_id, actor_role="technician",
            action="requote.command_received", target_type="work_orders",
            target_id=work_order_id,
            payload={"request_id": request_id, "reason": reason,
                     "initiated_via": initiated_via, "quote_id": new_quote_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("requote audit failed: %s", exc)
    return out, False
