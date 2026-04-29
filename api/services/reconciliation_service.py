"""Reconciliation 業務邏輯。

範圍：
  - listReconciliations（cursor + limit + status + technician_id）
  - approveReconciliation（pending → approved，並建立對應 settlement）

OpenAPI Reconciliation schema：
    id, technician_id, technician_name?, period_start, period_end,
    total_orders, total_revenue (decimal str), platform_fee?,
    technician_payout (decimal str), status (pending|approved|disputed),
    approved_by?, approved_at?, created_at

DB ↔ API 對齊：
  - reconciliations.{total_revenue, platform_fee, technician_payout} (FLOAT)
    → 2 位小數 decimal string
  - status DB 與 API enum 完全一致（pending/approved/disputed）
  - technicians.name JOIN 取出 → API technician_name

租戶隔離：reconciliations 沒 tenant_id，透過 JOIN technicians ON tenant_id 過濾。
approveReconciliation 同時 INSERT 一筆 settlement(amount = technician_payout,
status = 'pending', currency = 'TWD')，由結算寫入 pipeline 接手後續支付動作。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.reconciliation_service")


_VALID_STATUS = {"pending", "approved", "disputed"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    out: dict = {
        "id": str(row[0]),
        "technician_id": str(row[1]),
        "period_start": row[2].isoformat() if row[2] else None,
        "period_end": row[3].isoformat() if row[3] else None,
        "total_orders": int(row[4] or 0),
        "total_revenue": _coerce_decimal(row[5]),
        "platform_fee": _coerce_decimal(row[6]),
        "technician_payout": _coerce_decimal(row[7]),
        "status": row[8] or "pending",
        "approved_by": str(row[9]) if row[9] else None,
        "approved_at": row[10].isoformat() if row[10] else None,
        "created_at": row[11].isoformat() if row[11] else None,
    }
    if row[12]:
        out["technician_name"] = row[12]
    return out


_SELECT = (
    "r.id, r.technician_id, r.period_start, r.period_end, r.total_orders, "
    "r.total_revenue, r.platform_fee, r.technician_payout, r.status, "
    "r.approved_by, r.approved_at, r.created_at, t.name"
)

_JOIN = (
    "FROM reconciliations r "
    "JOIN technicians t ON r.technician_id = t.id"
)


async def list_reconciliations(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    technician_id: str | None = None,
) -> dict:
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
        where.append("r.status = %s")
        args.append(status)

    if technician_id:
        where.append("r.technician_id = %s::uuid")
        args.append(technician_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(r.created_at, r.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY r.created_at DESC, r.id DESC "
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
        next_cursor = encode_cursor({"ts": last[11].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


_APPROVE_FROM = {"pending"}


async def approve_reconciliation(
    *,
    tenant_id: str,
    recon_id: str,
    approver_user_id: str,
    note: str | None = None,
) -> dict:
    """pending → approved；同時建立 settlement(amount = technician_payout)。

    note 用於稽核軌跡（500 字內），目前 reconciliations 表沒 note 欄位，僅透過
    approved_by + approved_at 紀錄；保留參數以對齊 OpenAPI request body，未來
    可加 audit_logs 寫入或擴充 schema。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT r.status, r.technician_id, r.technician_payout {_JOIN} "
        f"WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)

    current_status = row[0]
    if current_status not in _APPROVE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot approve reconciliation in status '{current_status}'; expected 'pending'",
            409,
        )

    technician_id = str(row[1])
    payout = float(row[2] or 0)

    note_clean: str | None = None
    if note and note.strip():
        note_clean = note.strip()[:500]
    if note_clean:
        logger.info("reconciliation %s approved with note: %s", recon_id, note_clean)

    await db_module._conn.execute(
        "UPDATE reconciliations SET "
        "  status = 'approved', "
        "  approved_by = %s::uuid, "
        "  approved_at = NOW() "
        "WHERE id = %s::uuid",
        (approver_user_id, recon_id),
    )

    cur = await db_module._conn.execute(
        "INSERT INTO settlements "
        "  (reconciliation_id, technician_id, amount, currency, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'TWD', 'pending') "
        "RETURNING id, reconciliation_id, technician_id, amount, currency, "
        "          status, payment_method, paid_at, created_at",
        (recon_id, technician_id, payout),
    )
    s_row = await cur.fetchone()

    settlement: dict = {
        "id": str(s_row[0]),
        "reconciliation_id": str(s_row[1]),
        "technician_id": str(s_row[2]),
        "amount": _coerce_decimal(s_row[3]),
        "currency": (s_row[4] or "TWD"),
        "status": s_row[5] or "pending",
        "created_at": s_row[8].isoformat() if s_row[8] else None,
    }
    if s_row[6]:
        settlement["payment_method"] = s_row[6]
    if s_row[7] is not None:
        settlement["paid_at"] = s_row[7].isoformat()

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} {_JOIN} WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    r_row = await cur.fetchone()
    reconciliation = _row_to_dict(r_row)

    return {"reconciliation": reconciliation, "settlement": settlement}
