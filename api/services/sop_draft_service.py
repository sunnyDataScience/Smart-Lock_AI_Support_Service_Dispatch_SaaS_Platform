"""SOP Drafts 業務邏輯（Phase 1.11 read-only）。

範圍：listSopDrafts（cursor + limit + status 篩選）+ getSopDraft。
不含：reviewSopDraft / adoptSopDraft（寫入路徑等審核 + 家族覆核 pipeline）。

DB↔OpenAPI 欄位對齊：
  - source_problem_card_id (DB) → problem_card_id (API)
  - source_conversation_id  (DB) → 不暴露（API schema 沒此欄位）
  - reviewed_by             (DB) → reviewer_id (API)
  - case_event_id           (API) → 始終 None（DB 無對應欄位）
  - status mapping (DB 4-value → API 4-value):
      pending_review → under_review
      approved       → approved
      rejected       → rejected
      published      → approved   （已發布視為已核准的終態）
  - steps (JSONB) 由 service 層 coerce 為 list[{order,title,description}]，
    缺欄位則 best-effort 補齊（保證 API schema required 不違反）。
"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.sop_draft_service")


_DB_STATUS_TO_API = {
    "pending_review": "under_review",
    "approved": "approved",
    "rejected": "rejected",
    "published": "approved",
}

# 反向 mapping — API status filter → DB status 集合（一個 API 值可能對應多個 DB 值）
_API_STATUS_TO_DB = {
    "draft": [],  # DB 沒有 draft 狀態，API 篩選此值會返回空
    "under_review": ["pending_review"],
    "approved": ["approved", "published"],
    "rejected": ["rejected"],
}


_SELECT_COLUMNS = (
    "id, source_problem_card_id, title, steps, status, "
    "reviewed_by, reviewed_at, review_comment, created_at"
)


def _coerce_steps(raw) -> list[dict]:
    """把 DB JSONB steps 轉成 API SopDraftStep list。

    DB 沒有強制 schema；常見格式：
      [{"order":1,"title":"...","description":"..."}]
      [{"step":"...","detail":"..."}]            ← 舊格式
      [{"title":"...","desc":"..."}]             ← 前端 mock 格式
    缺欄位用 index + 1 / 空字串 fallback，保證符合 OpenAPI required。
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        order = item.get("order")
        if not isinstance(order, int) or order < 1:
            order = idx + 1
        title = (
            item.get("title")
            or item.get("step")
            or item.get("name")
            or f"Step {order}"
        )
        description = (
            item.get("description")
            or item.get("desc")
            or item.get("detail")
            or ""
        )
        out.append({
            "order": order,
            "title": str(title)[:200],
            "description": str(description)[:2000],
        })
    return out


def _row_to_dict(row: tuple) -> dict:
    db_status = (row[4] or "pending_review").lower()
    api_status = _DB_STATUS_TO_API.get(db_status, "under_review")
    return {
        "id": str(row[0]),
        "case_event_id": None,
        "problem_card_id": str(row[1]) if row[1] else None,
        "title": row[2] or "",
        "steps": _coerce_steps(row[3]),
        "status": api_status,
        "reviewer_id": str(row[5]) if row[5] else None,
        "reviewed_at": row[6].isoformat() if row[6] else None,
        "review_comment": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
    }


async def list_drafts(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        db_statuses = _API_STATUS_TO_DB.get(status, [])
        if not db_statuses:
            # 對應不到任何 DB 值 → 直接回空頁，省去查 DB
            return {"items": [], "next_cursor": None, "has_more": False}
        placeholders = ",".join(["%s"] * len(db_statuses))
        where.append(f"status IN ({placeholders})")
        args.extend(db_statuses)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM sop_drafts "
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
        next_cursor = encode_cursor({"ts": last[8].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_draft(*, tenant_id: str, draft_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM sop_drafts "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)
    return _row_to_dict(row)
