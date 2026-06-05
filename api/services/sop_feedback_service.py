"""SOP Feedback Service — FR-0051 Phase II MVP。

多源 feedback aggregate：customer_thumbs / technician_onsite / rma_finding /
ai_eval / csm_manual → 統一寫入 saas.sop_feedback → review queue +
impact tracking。

3 ops:
  - log_feedback: 寫一條 feedback row
  - list_feedback: list by sop_id / source / sentiment / date
  - get_sop_summary: 聚合單 sop_id by source / sentiment + sentiment_score
"""

from __future__ import annotations

import json
import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.sop_feedback_service")

_VALID_SOURCES = {
    "customer_thumbs", "technician_onsite", "rma_finding",
    "ai_eval", "csm_manual",
}
_VALID_SENTIMENTS = {"positive", "neutral", "negative"}
_VALID_SOP_TYPES = {"draft", "case_entry"}


async def log_feedback(
    *,
    tenant_id: str,
    sop_id: str,
    sop_type: str,
    source: str,
    sentiment: str,
    score: float | None = None,
    comment: str | None = None,
    metadata: dict | None = None,
    reporter_user_id: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    if sop_type not in _VALID_SOP_TYPES:
        raise ApiError("VALIDATION_ERROR", f"invalid sop_type: {sop_type}", 422)
    if source not in _VALID_SOURCES:
        raise ApiError("VALIDATION_ERROR", f"invalid source: {source}", 422)
    if sentiment not in _VALID_SENTIMENTS:
        raise ApiError("VALIDATION_ERROR", f"invalid sentiment: {sentiment}", 422)
    if score is not None and not (1.0 <= score <= 5.0):
        raise ApiError("VALIDATION_ERROR", "score must be 1.0..5.0 or null", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "INSERT INTO saas.sop_feedback "
        "  (tenant_id, sop_id, sop_type, source, sentiment, score, "
        "   comment, metadata, reporter_user_id, work_order_id) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, "
        "        %s::uuid, %s::uuid) "
        "RETURNING id, created_at",
        (
            tenant_id, sop_id, sop_type, source, sentiment, score,
            comment.strip()[:2000] if comment else None,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            reporter_user_id, work_order_id,
        ),
    )
    row = await cur.fetchone()
    return {
        "id": str(row[0]),
        "created_at": row[1].isoformat() if row[1] else None,
        "source": source,
        "sentiment": sentiment,
    }


async def list_feedback(
    *,
    tenant_id: str,
    sop_id: str | None = None,
    source: str | None = None,
    sentiment: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if sop_id:
        where.append("sop_id = %s::uuid")
        args.append(sop_id)
    if source:
        if source not in _VALID_SOURCES:
            raise ApiError("VALIDATION_ERROR", f"invalid source: {source}", 422)
        where.append("source = %s")
        args.append(source)
    if sentiment:
        if sentiment not in _VALID_SENTIMENTS:
            raise ApiError(
                "VALIDATION_ERROR", f"invalid sentiment: {sentiment}", 422,
            )
        where.append("sentiment = %s")
        args.append(sentiment)
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    args.append(limit)

    cur = await db_module._conn.execute(
        "SELECT id, sop_id, sop_type, source, sentiment, score, comment, "
        "       reporter_user_id, work_order_id, created_at "
        "FROM saas.sop_feedback "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "sop_id": str(r[1]),
            "sop_type": r[2],
            "source": r[3],
            "sentiment": r[4],
            "score": float(r[5]) if r[5] is not None else None,
            "comment": r[6],
            "reporter_user_id": str(r[7]) if r[7] else None,
            "work_order_id": str(r[8]) if r[8] else None,
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


async def get_sop_summary(
    *,
    tenant_id: str,
    sop_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """聚合單 sop_id：by_source / by_sentiment / avg_score / sentiment_score。

    sentiment_score = (positive - negative) / total × 100（-100..+100）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "sop_id = %s::uuid"]
    args: list = [tenant_id, sop_id]
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    base_where = " AND ".join(where)

    # by source
    cur = await db_module._conn.execute(
        "SELECT source, COUNT(*) FROM saas.sop_feedback "
        f"WHERE {base_where} GROUP BY source",
        tuple(args),
    )
    by_source = {r[0]: int(r[1]) for r in await cur.fetchall()}

    # by sentiment
    cur = await db_module._conn.execute(
        "SELECT sentiment, COUNT(*) FROM saas.sop_feedback "
        f"WHERE {base_where} GROUP BY sentiment",
        tuple(args),
    )
    by_sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    for r in await cur.fetchall():
        if r[0] in by_sentiment:
            by_sentiment[r[0]] = int(r[1])

    # avg_score
    cur = await db_module._conn.execute(
        "SELECT AVG(score) FROM saas.sop_feedback "
        f"WHERE {base_where} AND score IS NOT NULL",
        tuple(args),
    )
    avg_row = await cur.fetchone()
    avg_score = round(float(avg_row[0]), 2) if avg_row and avg_row[0] is not None else None

    total = sum(by_sentiment.values())
    pos = by_sentiment["positive"]
    neg = by_sentiment["negative"]
    sentiment_score = (
        round(100.0 * (pos - neg) / total, 2) if total > 0 else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "sop_id": sop_id,
        "window": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "total_feedback": total,
        "by_source": by_source,
        "by_sentiment": by_sentiment,
        "avg_score": avg_score,
        "sentiment_score": sentiment_score,  # -100..+100，越高越正面
    }
