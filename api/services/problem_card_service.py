"""ProblemCards 業務邏輯。

讀 problem_cards 表，mapping 成 OpenAPI schema：
  - problem_cards.symptoms (JSONB array) → ProblemCard.symptom (string)
  - problem_cards.status (incomplete/confirmed/resolved/escalated)
    → ProblemCardStatus (draft/confirmed/resolved)
  - problem_cards.urgency (low/normal/high/urgent)
    → Urgency (low/medium/high)
  - problem_cards.category NULL → "其他"
  - problem_cards.brand/model NULL → "" (避免違反 OpenAPI required)

租戶隔離：透過 conversations JOIN users.tenant_id。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.problem_card_service")


_DB_STATUS_TO_API = {
    "incomplete": "draft",
    "confirmed": "confirmed",
    "resolved": "resolved",
    "escalated": "resolved",  # OpenAPI 沒有 escalated；視為已結案
}

_DB_URGENCY_TO_API = {
    "low": "low",
    "normal": "medium",
    "high": "high",
    "urgent": "high",
}


def _coerce_symptom(symptoms) -> str:
    """JSONB array → 中文頓號分隔字串；長度超出 1000 字元截斷。"""
    if not symptoms:
        return ""
    if isinstance(symptoms, list):
        joined = "、".join(str(s) for s in symptoms if s)
    else:
        joined = str(symptoms)
    return joined[:1000]


def _coerce_status(db_status: str | None) -> str:
    if not db_status:
        return "draft"
    return _DB_STATUS_TO_API.get(db_status, "draft")


def _coerce_urgency(db_urgency: str | None) -> str:
    if not db_urgency:
        return "medium"
    return _DB_URGENCY_TO_API.get(db_urgency, "medium")


def _coerce_media_urls(media) -> list[str] | None:
    if not media:
        return None
    if isinstance(media, list):
        urls = [str(u) for u in media if u]
        return urls or None
    return None


def _pc_row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _PC_SELECT。"""
    return {
        "id": str(row[0]),
        "conversation_id": str(row[1]),
        "brand": row[2] or "",
        "model": row[3] or "",
        "symptom": _coerce_symptom(row[4]),
        "category": row[5] or "其他",
        "urgency": _coerce_urgency(row[6]),
        "confidence_score": None,
        "status": _coerce_status(row[7]),
        "media_urls": _coerce_media_urls(row[8]),
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


_PC_SELECT = (
    "pc.id, pc.conversation_id, pc.brand, pc.model, pc.symptoms, pc.category, "
    "pc.urgency, pc.status, pc.media_urls, pc.created_at, pc.updated_at"
)


async def list_cards(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    conversation_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if conversation_id:
        where.append("pc.conversation_id = %s::uuid")
        args.append(conversation_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(pc.created_at, pc.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_PC_SELECT} "
        f"FROM problem_cards pc "
        f"JOIN conversations c ON pc.conversation_id = c.id "
        f"JOIN users u ON c.user_id = u.id "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY pc.created_at DESC, pc.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_pc_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[9].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_card(*, tenant_id: str, pc_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_PC_SELECT} "
        f"FROM problem_cards pc "
        f"JOIN conversations c ON pc.conversation_id = c.id "
        f"JOIN users u ON c.user_id = u.id "
        f"WHERE pc.id = %s::uuid AND u.tenant_id = %s::uuid",
        (pc_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)
    return _pc_row_to_dict(row)


_CONFIRM_FROM = {"incomplete"}
_RESOLVE_FROM = {"confirmed"}


async def _fetch_status_for_update(pc_id: str, tenant_id: str) -> str:
    cur = await db_module._conn.execute(
        "SELECT pc.status "
        "FROM problem_cards pc "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND u.tenant_id = %s::uuid",
        (pc_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)
    return row[0]


async def confirm_card(*, tenant_id: str, pc_id: str) -> dict:
    """incomplete → confirmed。對齊 OpenAPI draft → confirmed。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(pc_id, tenant_id)
    if current not in _CONFIRM_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm problem card in status '{current}'; expected 'incomplete'",
            409,
        )
    await db_module._conn.execute(
        "UPDATE problem_cards SET status = 'confirmed', updated_at = NOW() "
        "WHERE id = %s::uuid",
        (pc_id,),
    )
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)


async def resolve_card(
    *, tenant_id: str, pc_id: str, resolution_layer: str,
) -> dict:
    """confirmed → resolved，記錄 resolution_layer (L1/L2/L3)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if resolution_layer not in {"L1", "L2", "L3"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "resolution_layer must be one of L1, L2, L3",
            422,
        )
    current = await _fetch_status_for_update(pc_id, tenant_id)
    if current not in _RESOLVE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot resolve problem card in status '{current}'; expected 'confirmed'",
            409,
        )
    await db_module._conn.execute(
        "UPDATE problem_cards SET "
        "  status = 'resolved', "
        "  resolution_layer = %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (resolution_layer, pc_id),
    )
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)
