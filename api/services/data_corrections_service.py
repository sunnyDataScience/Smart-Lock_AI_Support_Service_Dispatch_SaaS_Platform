"""DataCorrections review queue service。

對應 CR-0001 §1 / ADR-0029 三件組之 Review Queue：
agent/harness/data_correction.py 把 user 的 ``#資料修正`` 訊息寫進
``data_corrections`` 表（status='pending'），但之前**沒有 admin API
消費 pending queue**。本 service 補上 list / approve / reject。

決議 (CR-0001 §8 Q2 = 選項 b)：approve 動作不直接寫 fact，而是
產 sop_drafts 給 Knowledge Owner 二審後才進正式表，避免單一審核者
污染知識（對齊藍圖 sheet 05 S6→S7 知識螺旋）。

Schema 自帶 PK + status，本期 ALTER TABLE 補 reviewed_by / reviewed_at
/ review_note 三欄記錄稽核軌跡（idempotent）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.data_corrections_service")


_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_VALID_STATUSES = ("pending", "approved", "rejected")

_SCHEMA_INITIALIZED = False


async def _ensure_review_columns() -> None:
    """補 reviewed_by / reviewed_at / review_note 三欄（idempotent）。

    為什麼 service 層做 schema migration：data_corrections 表由 agent
    端建立（harness/data_correction.py:68），api 端歷史上沒碰過此表。
    純 ADD COLUMN IF NOT EXISTS 安全可重複；若未來改走 alembic 再
    搬到 migration script。
    """
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED:
        return
    if not await _ensure_conn():
        return
    try:
        await db_module._conn.execute("""
            ALTER TABLE data_corrections
                ADD COLUMN IF NOT EXISTS reviewed_by TEXT,
                ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS review_note TEXT
        """)
        _SCHEMA_INITIALIZED = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("data_corrections_schema_check_failed: %s", exc)


async def list_corrections(
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """List data corrections (cursor-paginated, newest first)。

    Args:
        status: 過濾狀態 (pending/approved/rejected)；None = 全部
        cursor: 上一次 next_cursor，會 decode 成 (created_at, id)
        limit: 1-100
    """
    await _ensure_review_columns()
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)

    limit = max(1, min(limit, _MAX_LIMIT))
    if status and status not in _VALID_STATUSES:
        raise ApiError("INVALID", f"invalid status: {status}", 400)

    where_parts = []
    args: list[Any] = []
    if status:
        where_parts.append("status = %s")
        args.append(status)
    if cursor:
        try:
            decoded = decode_cursor(cursor)
            cursor_ts = decoded.get("created_at")
            cursor_id = decoded.get("id")
            if cursor_ts and cursor_id is not None:
                where_parts.append("(created_at, id) < (%s, %s)")
                args.extend([cursor_ts, cursor_id])
        except Exception:  # noqa: BLE001 — 壞 cursor 回 400 比較友善
            raise ApiError("INVALID", "malformed cursor", 400) from None

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT id, user_id, note, conversation_context, user_facts, status,
               created_at, reviewed_by, reviewed_at, review_note
          FROM data_corrections
          {where_clause}
      ORDER BY created_at DESC, id DESC
         LIMIT %s
    """
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(row) for row in rows]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor({
            "created_at": last["created_at"],
            "id": last["id"],
        })

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_correction(correction_id: int) -> dict[str, Any]:
    await _ensure_review_columns()
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, user_id, note, conversation_context, user_facts, status, "
        "created_at, reviewed_by, reviewed_at, review_note "
        "FROM data_corrections WHERE id = %s",
        (correction_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"data_correction {correction_id} not found", 404)
    return _row_to_dict(row)


async def approve_correction(
    correction_id: int,
    *,
    reviewer_id: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    """Mark pending → approved。

    CR-0001 §8 Q2 (b): approve 後 entry **不直接改 user_facts**，由
    Knowledge Owner 之後透過 sop_drafts 流程把修正內容歸納成 SOP；
    本 endpoint 只負責狀態轉換 + 軌跡記錄。

    SOP draft 自動建立留 phase 2（需要對 conversation_context + note
    跑 LLM 摘要才有結構化 draft，本期超出 scope）。
    """
    return await _transition_status(
        correction_id,
        target="approved",
        reviewer_id=reviewer_id,
        review_note=review_note,
        allowed_from=("pending",),
    )


async def reject_correction(
    correction_id: int,
    *,
    reviewer_id: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    return await _transition_status(
        correction_id,
        target="rejected",
        reviewer_id=reviewer_id,
        review_note=review_note,
        allowed_from=("pending",),
    )


async def _transition_status(
    correction_id: int,
    *,
    target: str,
    reviewer_id: str,
    review_note: str | None,
    allowed_from: tuple[str, ...],
) -> dict[str, Any]:
    await _ensure_review_columns()
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)

    current = await get_correction(correction_id)
    if current["status"] not in allowed_from:
        raise ApiError(
            "CONFLICT",
            f"correction {correction_id} status is {current['status']}, "
            f"expected one of {allowed_from}",
            409,
        )

    cur = await db_module._conn.execute(
        "UPDATE data_corrections "
        "   SET status = %s, reviewed_by = %s, reviewed_at = NOW(), review_note = %s "
        " WHERE id = %s "
        " RETURNING id, user_id, note, conversation_context, user_facts, status, "
        "           created_at, reviewed_by, reviewed_at, review_note",
        (target, reviewer_id, review_note, correction_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"data_correction {correction_id} not found", 404)
    return _row_to_dict(row)


def _row_to_dict(row: tuple) -> dict[str, Any]:
    """psycopg row → API JSON-friendly dict。

    user_facts 欄位是 JSONB；psycopg 自動 deserialize 成 dict，故無需
    json.loads。created_at / reviewed_at 用 isoformat 序列化。
    """
    (id_, user_id, note, conversation_context, user_facts, status,
     created_at, reviewed_by, reviewed_at, review_note) = row
    return {
        "id": id_,
        "user_id": user_id,
        "note": note or "",
        "conversation_context": conversation_context,
        "user_facts": user_facts if isinstance(user_facts, dict) else (
            json.loads(user_facts) if user_facts else {}
        ),
        "status": status,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
        "reviewed_by": reviewed_by,
        "reviewed_at": (
            reviewed_at.isoformat() if isinstance(reviewed_at, datetime) else reviewed_at
        ),
        "review_note": review_note,
    }


__all__ = [
    "list_corrections",
    "get_correction",
    "approve_correction",
    "reject_correction",
]
