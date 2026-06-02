"""DataCorrections v2 service — tenant-scoped review queue（CR-0004 §8 / ADR-0029）。

決議：
  HD-1: 方案 B 就地補 tenant_id；WHERE tenant_id = %s 過濾
  HD-2: resolved 第四態 pending→approved→resolved（+ rejected）
  HD-3: approve 只改 status，SOP draft 自動建立延 phase 2（follow-up）
  HD-4: RBAC require_admin — 由 router 層透過 role_required("admin") 強制
  HD-5: GDPR PII（conversation_context/user_facts）— 標 follow-up FR-0053

比較 v1 service（data_corrections_service.py）:
  - 不再呼叫 _ensure_review_columns()（migration 009 已保證欄位存在）
  - list/get 加 tenant_id 過濾
  - _transition_status 加 tenant_id guard
  - 新增 resolve_correction（approved→resolved）
  - _VALID_STATUSES 加 resolved
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

logger = logging.getLogger("api.data_corrections_v2_service")

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100

# HD-2: 四態狀態機
_VALID_STATUSES = ("pending", "approved", "resolved", "rejected")


async def list_corrections_v2(
    *,
    tenant_id: str,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """List data corrections（tenant-scoped，cursor 分頁，newest first）。

    Args:
        tenant_id: 調用方 tenant（path 上的 tenantId，已由 router cross-tenant guard 比對）
        status: 過濾狀態（pending/approved/resolved/rejected）；None = 全部
        cursor: 上頁末 cursor（opaque base64）
        limit: 1-100
    """
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)

    limit = max(1, min(limit, _MAX_LIMIT))
    if status and status not in _VALID_STATUSES:
        raise ApiError("INVALID", f"invalid status: {status}", 400)

    where_parts: list[str] = ["tenant_id = %s"]
    args: list[Any] = [tenant_id]

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
        except Exception:  # noqa: BLE001
            raise ApiError("INVALID", "malformed cursor", 400) from None

    where_clause = "WHERE " + " AND ".join(where_parts)

    sql = f"""
        SELECT id, user_id, note, conversation_context, user_facts, status,
               created_at, reviewed_by, reviewed_at, review_note, tenant_id
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


async def get_correction_v2(
    *,
    tenant_id: str,
    correction_id: int,
) -> dict[str, Any]:
    """取單筆資料修正（tenant-scoped；404 if not found or belongs to other tenant）。"""
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT id, user_id, note, conversation_context, user_facts, status, "
        "       created_at, reviewed_by, reviewed_at, review_note, tenant_id "
        "  FROM data_corrections "
        " WHERE id = %s AND tenant_id = %s",
        (correction_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"data_correction {correction_id} not found", 404)
    return _row_to_dict(row)


async def approve_correction_v2(
    *,
    tenant_id: str,
    correction_id: int,
    reviewer_id: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    """pending → approved（HD-3: 只改 status，SOP draft 自動建立延 phase 2）。"""
    return await _transition_status(
        tenant_id=tenant_id,
        correction_id=correction_id,
        target="approved",
        reviewer_id=reviewer_id,
        review_note=review_note,
        allowed_from=("pending",),
    )


async def reject_correction_v2(
    *,
    tenant_id: str,
    correction_id: int,
    reviewer_id: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    """pending → rejected。"""
    return await _transition_status(
        tenant_id=tenant_id,
        correction_id=correction_id,
        target="rejected",
        reviewer_id=reviewer_id,
        review_note=review_note,
        allowed_from=("pending",),
    )


async def resolve_correction_v2(
    *,
    tenant_id: str,
    correction_id: int,
    reviewer_id: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    """approved → resolved（HD-2 第四態；Knowledge Owner 完成知識螺旋後標記）。

    SOP draft 自動建立留 phase 2（需對 conversation_context + note 跑 LLM 摘要；
    本期超出 scope，標 follow-up HD-3）。
    """
    return await _transition_status(
        tenant_id=tenant_id,
        correction_id=correction_id,
        target="resolved",
        reviewer_id=reviewer_id,
        review_note=review_note,
        allowed_from=("approved",),
    )


async def _transition_status(
    *,
    tenant_id: str,
    correction_id: int,
    target: str,
    reviewer_id: str,
    review_note: str | None,
    allowed_from: tuple[str, ...],
) -> dict[str, Any]:
    if not await _ensure_conn():
        raise ApiError("INTERNAL", "data_corrections DB unavailable", 503)

    # 讀取時已含 tenant_id guard（get_correction_v2 回 404 if cross-tenant or not found）
    current = await get_correction_v2(tenant_id=tenant_id, correction_id=correction_id)
    if current["status"] not in allowed_from:
        raise ApiError(
            "CONFLICT",
            f"correction {correction_id} status is '{current['status']}', "
            f"expected one of {allowed_from}",
            409,
        )

    cur = await db_module._conn.execute(
        "UPDATE data_corrections "
        "   SET status = %s, reviewed_by = %s, reviewed_at = NOW(), review_note = %s "
        " WHERE id = %s AND tenant_id = %s "
        " RETURNING id, user_id, note, conversation_context, user_facts, status, "
        "           created_at, reviewed_by, reviewed_at, review_note, tenant_id",
        (target, reviewer_id, review_note, correction_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"data_correction {correction_id} not found", 404)
    return _row_to_dict(row)


def _row_to_dict(row: tuple) -> dict[str, Any]:
    """psycopg row → API JSON-friendly dict。

    欄順序（11 欄，與 migration 009 對齊）：
      id, user_id, note, conversation_context, user_facts, status,
      created_at, reviewed_by, reviewed_at, review_note, tenant_id
    """
    (id_, user_id, note, conversation_context, user_facts, status,
     created_at, reviewed_by, reviewed_at, review_note, tenant_id) = row
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
        "tenant_id": str(tenant_id) if tenant_id else None,
    }


__all__ = [
    "list_corrections_v2",
    "get_correction_v2",
    "approve_correction_v2",
    "reject_correction_v2",
    "resolve_correction_v2",
]
