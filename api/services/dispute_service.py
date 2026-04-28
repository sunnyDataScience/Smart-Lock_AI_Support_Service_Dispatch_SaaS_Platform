"""Disputes 業務邏輯（Phase 1.25 read-only）。

範圍：listDisputes（cursor + limit + status + dispute_type + work_order_id）、getDispute。
不含：submitDisputeResolution（write，需 Idempotency-Key + 證據檔案上傳，不在本 phase）。

OpenAPI Dispute schema：
    id, filed_by, dispute_type (5 enum), status (5 enum), description,
    filed_at, created_at, updated_at；optional: work_order_id, invoice_id,
    evidence (jsonb), resolution, resolution_amount (decimal str), resolved_by,
    resolved_at, sla_deadline.

DB ↔ API 對齊：
  - dispute_type (varchar(50))   → API DisputeType；非預期值視為 quality（避免破壞 enum）
  - status (varchar(50))         → API DisputeStatus；非預期值視為 filed
  - resolution_amount (FLOAT)    → decimal string with 2 decimals；NULL → None
  - evidence (jsonb)             → 直通；NULL → None

租戶隔離：disputes 沒 tenant_id，透過 filed_by → users.tenant_id 1-level JOIN
（與 warranty_claims customer_id 同 pattern）。
"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.dispute_service")


_VALID_API_TYPE = {"pricing", "quality", "warranty", "cancellation_fee", "settlement"}
_VALID_API_STATUS = {"filed", "in_review", "resolved", "rejected", "closed"}


def _coerce_type(raw: str | None) -> str:
    if raw and raw in _VALID_API_TYPE:
        return raw
    return "quality"


def _coerce_status(raw: str | None) -> str:
    if raw and raw in _VALID_API_STATUS:
        return raw
    return "filed"


def _coerce_decimal(amount) -> str | None:
    if amount is None:
        return None
    return f"{float(amount):.2f}"


def _coerce_evidence(raw):
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return None
    return None


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "invoice_id": str(row[2]) if row[2] else None,
        "filed_by": str(row[3]),
        "dispute_type": _coerce_type(row[4]),
        "status": _coerce_status(row[5]),
        "description": row[6] or "",
        "evidence": _coerce_evidence(row[7]),
        "resolution": row[8],
        "resolution_amount": _coerce_decimal(row[9]),
        "resolved_by": str(row[10]) if row[10] else None,
        "filed_at": row[11].isoformat() if row[11] else None,
        "resolved_at": row[12].isoformat() if row[12] else None,
        "sla_deadline": row[13].isoformat() if row[13] else None,
        "created_at": row[14].isoformat() if row[14] else None,
        "updated_at": row[15].isoformat() if row[15] else None,
    }


_SELECT = (
    "d.id, d.work_order_id, d.invoice_id, d.filed_by, d.dispute_type, d.status, "
    "d.description, d.evidence, d.resolution, d.resolution_amount, d.resolved_by, "
    "d.filed_at, d.resolved_at, d.sla_deadline, d.created_at, d.updated_at"
)

_TENANT_JOIN = "FROM disputes d JOIN users u ON d.filed_by = u.id"


async def list_disputes(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    dispute_type: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_API_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("d.status = %s")
        args.append(status)

    if dispute_type:
        if dispute_type not in _VALID_API_TYPE:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid dispute_type filter: {dispute_type}",
                422,
            )
        where.append("d.dispute_type = %s")
        args.append(dispute_type)

    if work_order_id:
        where.append("d.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(d.created_at, d.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY d.created_at DESC, d.id DESC "
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
        next_cursor = encode_cursor({"ts": last[14].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_dispute(*, tenant_id: str, dispute_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE d.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (dispute_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)
    return _row_to_dict(row)
