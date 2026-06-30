"""Settlements 業務邏輯（Phase 1.13 read-only）。

範圍：listSettlements（cursor + limit + status + technician_id 篩選）。
不含：approveReconciliation / submitRefundDecision / 對帳寫入路徑。

OpenAPI Settlement schema：
    id, reconciliation_id, technician_id, technician_name?, amount (decimal str),
    currency (TWD), status (pending|paid|failed), payment_method?, paid_at?, created_at

DB ↔ API 對齊：
  - settlements.amount (FLOAT) → API amount: decimal string with 2 decimals
  - settlements.currency        → 直通；DB 保留 NULL fallback 為 'TWD'
  - settlements.status (pending|paid|failed) → 直通（DB 三值與 API enum 完全一致）
  - settlements.payment_method (bank_transfer|other) → 直通
  - technicians.name JOIN 取出 → API technician_name

租戶隔離：settlements 沒有 tenant_id；透過 JOIN technicians ON tenant_id 過濾。
所有結算列都必須對應一位 technician（DB FK NOT NULL on FK ref，但實務上 ON DELETE
RESTRICT 會擋住孤兒列），所以 INNER JOIN 安全。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.settlement_service")


_VALID_STATUS = {"pending", "paid", "failed"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序：
    s.id, s.reconciliation_id, s.technician_id, s.amount, s.currency,
    s.status, s.payment_method, s.paid_at, s.created_at, t.name,
    r.period_end
    """
    out: dict = {
        "id": str(row[0]),
        "reconciliation_id": str(row[1]),
        "technician_id": str(row[2]),
        "amount": _coerce_decimal(row[3]),
        "currency": (row[4] or "TWD"),
        "status": row[5] or "pending",
        "created_at": row[8].isoformat() if row[8] else None,
    }
    if row[9]:
        out["technician_name"] = row[9]
    if row[6]:
        out["payment_method"] = row[6]
    if row[7] is not None:
        out["paid_at"] = row[7].isoformat()
    if len(row) > 10 and row[10] is not None:
        out["period_end"] = row[10].isoformat()
    return out


_SELECT = (
    "s.id, s.reconciliation_id, s.technician_id, s.amount, s.currency, "
    "s.status, s.payment_method, s.paid_at, s.created_at, t.name, "
    "r.period_end"
)

_JOIN = (
    "FROM settlements s "
    "JOIN technicians t ON s.technician_id = t.id "
    "JOIN reconciliations r ON s.reconciliation_id = r.id"
)


async def list_settlements(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    technician_id: str | None = None,
    period_filter: str | None = None,
    sort_by: str | None = None,
) -> dict:
    """列 settlements。

    period_filter:
      - None: 不過濾（v1 預設行為，向後相容）
      - "last_3_months": 僅取 r.period_end >= NOW() - INTERVAL '3 months'（CR-0008 HD-01 v2 預設）
      - "last_12_months": 12 個月版
    sort_by:
      - None: ORDER BY s.created_at DESC（v1 預設）
      - "period_end_desc": ORDER BY r.period_end DESC, s.created_at DESC（CR-0008 HD-02 v2 預設）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["t.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("s.status = %s")
        args.append(status)

    if technician_id:
        where.append("s.technician_id = %s::uuid")
        args.append(technician_id)

    if period_filter == "last_3_months":
        where.append("r.period_end >= (NOW() - INTERVAL '3 months')::date")
    elif period_filter == "last_12_months":
        where.append("r.period_end >= (NOW() - INTERVAL '12 months')::date")
    elif period_filter is not None:
        raise ApiError(
            "VALIDATION_ERROR",
            f"Invalid period_filter: {period_filter}",
            422,
        )

    # cursor 跟著 sort 維度走
    use_period_sort = sort_by == "period_end_desc"
    cur_data = decode_cursor(cursor)
    if cur_data:
        if use_period_sort and "pe" in cur_data and "id" in cur_data:
            where.append("(r.period_end, s.id) < (%s::date, %s::uuid)")
            args.extend([cur_data["pe"], cur_data["id"]])
        elif "ts" in cur_data and "id" in cur_data:
            where.append("(s.created_at, s.id) < (%s, %s::uuid)")
            args.extend([cur_data["ts"], cur_data["id"]])

    order_clause = (
        "ORDER BY r.period_end DESC, s.created_at DESC, s.id DESC"
        if use_period_sort
        else "ORDER BY s.created_at DESC, s.id DESC"
    )

    sql = (
        f"SELECT {_SELECT} {_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"{order_clause} "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_dict(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        if use_period_sort:
            next_cursor = encode_cursor({"pe": last[10].isoformat(), "id": str(last[0])})
        else:
            next_cursor = encode_cursor({"ts": last[8].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# ─────────────────────────────────────────────────────────────────────────────
# batch_action — 批次 confirm / mark_paid
# ─────────────────────────────────────────────────────────────────────────────

async def batch_action(
    *,
    tenant_id: str,
    settlement_ids: list[str],
    action: str,
    payment_method: str | None = None,
    notes: str | None = None,
) -> dict:
    """批次 settlement 操作.

    action='confirm': pending → confirmed (僅當前 pending 才會生效)
    action='mark_paid': confirmed → paid + paid_at=NOW + payment_method
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if action not in {"confirm", "mark_paid"}:
        raise ApiError(
            "VALIDATION_ERROR", f"Invalid action: {action}", 422,
        )

    if not settlement_ids:
        return {"updated": 0, "skipped": 0}

    # CR — batch 改寫 public.settlements（與 list_settlements 同表）。原寫
    # saas.settlement（空表，generate 月結批次的 v2 目標）→ 批次更新 0 筆、前端看似
    # 「沒反應」。public.settlements 無 tenant_id 欄，沿 list 慣例透過 technicians.
    # tenant_id 過濾；亦無 manual_paid_at 欄故不設。status 為自由 varchar（無 CHECK），
    # 'confirmed' 中間態可直接寫入。
    tech_scope = (
        "technician_id IN (SELECT id FROM technicians WHERE tenant_id = %s::uuid)"
    )
    if action == "confirm":
        sql = (
            "UPDATE settlements "
            "SET status = 'confirmed' "
            "WHERE id = ANY(%s::uuid[]) "
            "  AND status = 'pending' "
            f"  AND {tech_scope}"
        )
        cur = await db_module._conn.execute(
            sql, (settlement_ids, tenant_id),
        )
        updated = cur.rowcount
    else:  # mark_paid
        sql = (
            "UPDATE settlements "
            "SET status = 'paid', "
            "    paid_at = NOW(), "
            "    payment_method = COALESCE(%s, payment_method) "
            "WHERE id = ANY(%s::uuid[]) "
            "  AND status IN ('confirmed', 'pending') "
            f"  AND {tech_scope}"
        )
        cur = await db_module._conn.execute(
            sql, (payment_method, settlement_ids, tenant_id),
        )
        updated = cur.rowcount

    skipped = len(settlement_ids) - updated
    return {
        "updated": updated,
        "skipped": skipped,
        "action": action,
    }
