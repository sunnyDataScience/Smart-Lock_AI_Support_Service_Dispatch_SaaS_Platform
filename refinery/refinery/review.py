"""審核層 — draft 讀取與狀態轉移(15_SDS §9.2 狀態機/CR-0140)。

轉移(僅 pending_review 可動作;HITL 硬 gate:approve 時才呼叫 Publisher):
  pending_review → approved(事實軌落 case_entries;行為軌產 patch artifact)
                 → rejected(留 audit)
                 → re_refine(2.3.1 intake 重撿,舊 draft 屆時標 superseded)
"""

from datetime import datetime, timezone
from typing import Callable

import psycopg

from . import publisher

_DRAFT_COLS = (
    "id", "draft_key", "draft_type", "source_problem_card_id", "source_conversation_id",
    "brand", "model", "category", "title", "payload", "provenance", "confidence",
    "status", "review_comment", "reviewed_by", "reviewed_at", "created_at", "updated_at",
)


class ReviewError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _row_to_draft(row: tuple) -> dict:
    d = dict(zip(_DRAFT_COLS, row))
    for k in ("source_problem_card_id", "source_conversation_id", "reviewed_by"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("reviewed_at", "created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def list_drafts(conn: psycopg.Connection, tenant: str, *, status: str | None = None,
                limit: int = 100) -> list[dict]:
    sql = f"SELECT {', '.join(_DRAFT_COLS)} FROM knowledge_drafts WHERE tenant_id = %s"
    params: list = [tenant]
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [_row_to_draft(r) for r in cur.fetchall()]


def get_draft(conn: psycopg.Connection, tenant: str, draft_id: int) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_DRAFT_COLS)} FROM knowledge_drafts "
            "WHERE tenant_id = %s AND id = %s",
            (tenant, draft_id),
        )
        row = cur.fetchone()
    if row is None:
        raise ReviewError("DRAFT_NOT_FOUND", f"draft {draft_id} 不存在", 404)
    return _row_to_draft(row)


def _transition(conn: psycopg.Connection, tenant: str, draft_id: int, *,
                to_status: str, reviewer_id: str, comment: str | None) -> None:
    """pending_review → to_status(樂觀鎖:WHERE status='pending_review')。不 commit。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE knowledge_drafts
            SET status = %s, review_comment = %s, reviewed_by = %s::uuid,
                reviewed_at = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status = 'pending_review'
            """,
            (to_status, comment, reviewer_id,
             datetime.now(timezone.utc), tenant, draft_id),
        )
        if cur.rowcount == 0:
            raise ReviewError(
                "INVALID_TRANSITION",
                f"draft {draft_id} 非 pending_review,不可轉 {to_status}",
            )


def approve(conn: psycopg.Connection, tenant: str, draft_id: int, *,
            reviewer_id: str, comment: str | None,
            embed_fn: Callable[[str], list[float]],
            embed_model_name: str) -> dict:
    """核可:先轉移(佔鎖)再落地;同一交易,落地失敗全回滾(核可前絕不落地的反向保證)。"""
    draft = get_draft(conn, tenant, draft_id)
    _transition(conn, tenant, draft_id, to_status="approved",
                reviewer_id=reviewer_id, comment=comment)
    if draft["draft_type"] == "case_entry":
        case_id = publisher.publish_case_entry(
            conn, tenant, draft,
            reviewer_id=reviewer_id, embed_fn=embed_fn, embed_model_name=embed_model_name,
        )
        published = {"kind": "case_entry", "case_entry_id": case_id,
                     "embedding_model": embed_model_name}
    else:
        published = {"kind": "behavior_patch", **publisher.behavior_patch_artifact(draft)}
    publisher.record_publish_result(conn, tenant, draft_id, published)
    conn.commit()
    return published


def reject(conn: psycopg.Connection, tenant: str, draft_id: int, *,
           reviewer_id: str, comment: str | None) -> None:
    _transition(conn, tenant, draft_id, to_status="rejected",
                reviewer_id=reviewer_id, comment=comment)
    conn.commit()


def re_refine(conn: psycopg.Connection, tenant: str, draft_id: int, *,
              reviewer_id: str, comment: str | None) -> None:
    _transition(conn, tenant, draft_id, to_status="re_refine",
                reviewer_id=reviewer_id, comment=comment)
    conn.commit()
