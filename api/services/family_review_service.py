"""Family Review 業務邏輯。

範圍：
  - list_pending  → sop_drafts.status='approved' AND 尚未有 family_reviews 紀錄
  - list_history  → family_reviews 列表（cursor 分頁，可 action filter）
  - create        → 對單筆 sop_draft 建立家族覆核（action: approved/rejected）

設計：
  - 一筆 sop_draft 僅一筆 family_review（DB uniq 約束）；重複提交回 409 CONFLICT。
  - rejected 不退回 sop_drafts.status，僅留覆核紀錄；後續流程由人工另開新版本草稿處理。
  - awaiting_family_review_since 取自 sop_drafts.reviewed_at（管理員初審通過時間）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.family_review_service")


_ACTION_VALUES = {"approved", "rejected"}

_REVIEW_COLUMNS = "id, sop_draft_id, action, reviewer_id, comment, created_at"


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "sop_draft_id": str(row[1]),
        "action": row[2],
        "reviewer_id": str(row[3]),
        "comment": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


async def list_pending(*, tenant_id: str) -> list[dict]:
    """SOP 草稿初審通過、尚未家族覆核的清單。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        "SELECT sd.id, sd.title, u.email, sd.reviewed_at "
        "FROM sop_drafts sd "
        "LEFT JOIN users u ON sd.reviewed_by = u.id "
        "WHERE sd.tenant_id = %s::uuid "
        "  AND LOWER(sd.status) = 'approved' "
        "  AND sd.reviewed_at IS NOT NULL "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM family_reviews fr WHERE fr.sop_draft_id = sd.id"
        "  ) "
        "ORDER BY sd.reviewed_at ASC, sd.id ASC"
    )
    cur = await db_module._conn.execute(sql, [tenant_id])
    rows = await cur.fetchall()

    items = []
    for row in rows:
        approved_at = row[3].isoformat() if row[3] else None
        item = {
            "sop_draft_id": str(row[0]),
            "title": row[1] or "",
            "awaiting_family_review_since": approved_at,
        }
        if row[2]:
            item["admin_reviewer"] = row[2]
        if approved_at:
            item["admin_approved_at"] = approved_at
        items.append(item)
    return items


async def list_history(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    action: str | None,
) -> dict:
    """家族覆核歷史（cursor 分頁；可 action filter）。"""
    if action is not None and action not in _ACTION_VALUES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"action must be one of {sorted(_ACTION_VALUES)}",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if action:
        where.append("action = %s")
        args.append(action)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_REVIEW_COLUMNS} "
        f"FROM family_reviews "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY created_at DESC, id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[5].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def create_review(
    *,
    tenant_id: str,
    sop_draft_id: str,
    action: str,
    comment: str | None,
    reviewer_id: str,
) -> dict:
    """建立家族覆核。

    驗證：
      - action ∈ {approved, rejected}
      - comment ≤ 1000
      - sop_draft 存在於 tenant
      - sop_draft.status = 'approved'（未經初審不得進入家族覆核）
      - 同一 sop_draft 不可重複覆核（DB uniq → 409 CONFLICT）
    """
    if action not in _ACTION_VALUES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"action must be one of {sorted(_ACTION_VALUES)}",
            422,
        )
    if comment is not None and len(comment) > 1000:
        raise ApiError(
            "VALIDATION_ERROR",
            "comment too long (max 1000 chars)",
            422,
        )
    if not reviewer_id:
        raise ApiError("UNAUTHENTICATED", "reviewer_id missing", 401)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # Validate draft exists, in tenant, status=approved
    cur = await db_module._conn.execute(
        "SELECT status FROM sop_drafts "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (sop_draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)
    if (row[0] or "").lower() != "approved":
        raise ApiError(
            "CONFLICT",
            "Only admin-approved SOP drafts can be submitted for family review",
            409,
        )

    # Insert (uniq on sop_draft_id will reject dup)
    try:
        cur = await db_module._conn.execute(
            f"INSERT INTO family_reviews (tenant_id, sop_draft_id, action, reviewer_id, comment) "
            f"VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s) "
            f"RETURNING {_REVIEW_COLUMNS}",
            (tenant_id, sop_draft_id, action, reviewer_id, comment),
        )
        inserted = await cur.fetchone()
    except Exception as e:
        msg = str(e).lower()
        if "uniq_family_review_draft" in msg or "unique" in msg:
            raise ApiError(
                "CONFLICT",
                "Family review already exists for this SOP draft",
                409,
            )
        raise

    if not inserted:
        raise ApiError("INTERNAL_ERROR", "Insert returned no row", 500)
    return _row_to_dict(inserted)
