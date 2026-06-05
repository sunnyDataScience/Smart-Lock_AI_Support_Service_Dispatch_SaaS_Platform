"""SOP Performance Service — WBS §8 P1「SOP 績效真實化」backend。

提供 SOP 績效真實 metrics 取代前端 placeholder「開發中」。

範圍（基於現有 sop_drafts schema，不新增欄位）：
  - 總 SOP 數 / 各 status 分布
  - approval_rate = approved / (approved + rejected)
  - publish_rate = published / approved
  - window_days 內新增 / 已 published 數
  - top_recent_published（最近 published 5 筆，給前端展示熱榜）
  - retire_candidates（30 日內無新增且 published 的 SOP — 候 retire）

不依賴新表，純由 sop_drafts 聚合 + JOIN case_entries 補追溯。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.sop_performance_service")


async def get_sop_metrics(
    *, tenant_id: str, window_days: int = 30,
) -> dict:
    """聚合 SOP 績效 metrics。

    Returns:
      {
        "tenant_id": str,
        "window_days": 30,
        "status_distribution": {pending_review, approved, rejected, published},
        "totals": {
          "total": int, "deleted": int, "active": int,
        },
        "rates": {
          "approval_rate_pct": float,  # approved / (approved+rejected)
          "publish_rate_pct": float,   # published / approved
        },
        "window": {
          "new_drafts": int,           # 30 日內新增（不含 deleted）
          "newly_published": int,      # 30 日內 reviewed_at→published
        },
        "top_recent_published": [
          {"id", "title", "reviewed_at", "case_entry_id"}, ...  # 最多 5 筆
        ],
        "retire_candidates_count": int,  # published 但 >= window_days 未動
      }
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if window_days < 1 or window_days > 365:
        raise ApiError("VALIDATION_ERROR", "window_days must be 1..365", 422)

    # 1. status distribution + totals (active = NOT deleted)
    cur = await db_module._conn.execute(
        "SELECT status, COUNT(*) FROM sop_drafts "
        "WHERE tenant_id = %s::uuid AND deleted_at IS NULL "
        "GROUP BY status",
        (tenant_id,),
    )
    rows = await cur.fetchall()
    status_dist = {
        "pending_review": 0, "approved": 0,
        "rejected": 0, "published": 0,
    }
    for status, count in rows:
        if status in status_dist:
            status_dist[status] = int(count)

    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE deleted_at IS NULL), "
        "  COUNT(*) FILTER (WHERE deleted_at IS NOT NULL), "
        "  COUNT(*) "
        "FROM sop_drafts WHERE tenant_id = %s::uuid",
        (tenant_id,),
    )
    totals_row = await cur.fetchone()
    active = int(totals_row[0] or 0)
    deleted = int(totals_row[1] or 0)
    total = int(totals_row[2] or 0)

    # 2. rates
    approved = status_dist["approved"]
    rejected = status_dist["rejected"]
    published = status_dist["published"]
    decided = approved + rejected
    approval_rate = (
        round(100.0 * approved / decided, 2) if decided > 0 else 0.0
    )
    publish_rate = (
        round(100.0 * published / approved, 2) if approved > 0 else 0.0
    )

    # 3. window — 30 日內新增 / 已 published
    cur = await db_module._conn.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE created_at >= NOW() - (%s || ' days')::interval), "
        "  COUNT(*) FILTER (WHERE status = 'published' "
        "                   AND reviewed_at >= NOW() - (%s || ' days')::interval) "
        "FROM sop_drafts WHERE tenant_id = %s::uuid AND deleted_at IS NULL",
        (str(window_days), str(window_days), tenant_id),
    )
    win_row = await cur.fetchone()
    new_drafts = int(win_row[0] or 0)
    newly_published = int(win_row[1] or 0)

    # 4. top_recent_published (最多 5)
    cur = await db_module._conn.execute(
        "SELECT id, title, reviewed_at, published_as_case_entry_id "
        "FROM sop_drafts "
        "WHERE tenant_id = %s::uuid "
        "  AND status = 'published' AND deleted_at IS NULL "
        "ORDER BY reviewed_at DESC NULLS LAST "
        "LIMIT 5",
        (tenant_id,),
    )
    top_rows = await cur.fetchall()
    top_recent_published = [
        {
            "id": str(r[0]),
            "title": r[1],
            "reviewed_at": r[2].isoformat() if r[2] else None,
            "case_entry_id": str(r[3]) if r[3] else None,
        }
        for r in top_rows
    ]

    # 5. retire_candidates_count — published 且 reviewed_at < NOW-window
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM sop_drafts "
        "WHERE tenant_id = %s::uuid AND deleted_at IS NULL "
        "  AND status = 'published' "
        "  AND reviewed_at < NOW() - (%s || ' days')::interval",
        (tenant_id, str(window_days)),
    )
    retire_row = await cur.fetchone()
    retire_candidates_count = int(retire_row[0] or 0)

    return {
        "tenant_id": tenant_id,
        "window_days": window_days,
        "status_distribution": status_dist,
        "totals": {
            "total": total, "deleted": deleted, "active": active,
        },
        "rates": {
            "approval_rate_pct": approval_rate,
            "publish_rate_pct": publish_rate,
        },
        "window": {
            "new_drafts": new_drafts,
            "newly_published": newly_published,
        },
        "top_recent_published": top_recent_published,
        "retire_candidates_count": retire_candidates_count,
    }
