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

import hashlib
import logging

import psycopg

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

# ── TI-A10-02：家族覆核不可篡改 ledger hash chain（合約 4.4d）──
_FR_GENESIS = "GENESIS"
# CR-0166 R1-5：家族覆核鏈的 advisory xact-lock key（獨立於 audit_events 鏈）
_FR_CHAIN_LOCK_KEY = 0x10C_FA317


def _fr_canonical(sop_draft_id: str, action: str, reviewer_id: str, comment: str | None) -> str:
    return "\x1f".join([sop_draft_id, action, reviewer_id, comment or ""])


def _fr_entry_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{content}".encode("utf-8")).hexdigest()


async def _fr_latest_hash() -> str:
    cur = await db_module._conn.execute(
        "SELECT entry_hash FROM family_reviews WHERE entry_hash IS NOT NULL "
        "ORDER BY created_at DESC, id DESC LIMIT 1")
    row = await cur.fetchone()
    return row[0] if row and row[0] else _FR_GENESIS


async def verify_family_review_ledger(*, limit: int = 1000) -> dict:
    """驗家族覆核 ledger 完整性（hash chain）。回 {checked, valid, broken_at}。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, sop_draft_id, action, reviewer_id, comment, prev_hash, entry_hash "
        "FROM family_reviews WHERE entry_hash IS NOT NULL "
        "ORDER BY created_at ASC, id ASC LIMIT %s", (limit,))
    expected_prev = _FR_GENESIS
    checked = 0
    for r in await cur.fetchall():
        checked += 1
        content = _fr_canonical(str(r[1]), r[2], str(r[3]), r[4])
        recomputed = _fr_entry_hash(r[5] or _FR_GENESIS, content)
        if recomputed != r[6] or (r[5] or _FR_GENESIS) != expected_prev:
            return {"checked": checked, "valid": False, "broken_at": str(r[0])}
        expected_prev = r[6]
    return {"checked": checked, "valid": True, "broken_at": None}

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

    # Validate draft exists, in tenant, status=approved + 取初審 reviewed_by 做雙審 distinct
    cur = await db_module._conn.execute(
        "SELECT status, reviewed_by FROM sop_drafts "
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
    # TI-A10-02 / 合約 4.4(d)：高風險 SOP 雙審 —— 家族覆核者須異於初審 admin
    # （Knowledge Owner ≠ domain expert，四眼），同人不得兩審。
    admin_reviewer = row[1]
    if admin_reviewer and str(admin_reviewer) == str(reviewer_id):
        raise ApiError(
            "SOD_VIOLATION",
            "family reviewer must differ from initial admin reviewer (dual-review)",
            403,
        )

    # TI-A10-02：不可篡改 ledger —— 計 hash chain（接前一列 entry_hash）
    # CR-0166 R1-5：advisory xact-lock 序列化「讀末 hash → INSERT」，防不同 draft
    # 並發插入時讀同一 prev_hash 造成鏈分叉（同 draft 由 uniq 擋，跨 draft 靠此鎖）。
    try:
        async with db_module._conn.transaction():
            await db_module._conn.execute("SET LOCAL lock_timeout = '2s'")
            await db_module._conn.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_FR_CHAIN_LOCK_KEY,)
            )
            prev_hash = await _fr_latest_hash()
            entry_hash = _fr_entry_hash(
                prev_hash, _fr_canonical(sop_draft_id, action, reviewer_id, comment))
            cur = await db_module._conn.execute(
                f"INSERT INTO family_reviews "
                f"  (tenant_id, sop_draft_id, action, reviewer_id, comment, prev_hash, entry_hash) "
                f"VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s) "
                f"RETURNING {_REVIEW_COLUMNS}",
                (tenant_id, sop_draft_id, action, reviewer_id, comment, prev_hash, entry_hash),
            )
            inserted = await cur.fetchone()
    except psycopg.Error as e:
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
