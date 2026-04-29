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

import json
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


# PATCH 不允許改 status；狀態請走 /confirm 或 /resolve（避免 state machine 被旁路）
_API_URGENCY_TO_DB = {"low": "low", "medium": "normal", "high": "high"}
_VALID_API_URGENCY = set(_API_URGENCY_TO_DB)
_API_STATUS_TO_DB = {"draft": "incomplete", "confirmed": "confirmed", "resolved": "resolved"}
_VALID_API_STATUS = set(_API_STATUS_TO_DB)


_VALID_DOOR_STATUS = {"locked_out", "partially_functional", "normal"}
_VALID_NETWORK_STATUS = {"online", "offline", "unknown"}

# OpenAPI intent enum → DB intent vocabulary（DB 存 inquiry/repair/complaint/other）
_API_INTENT_TO_DB = {
    "unlock_request": "repair",
    "repair_request": "repair",
    "installation": "other",
    "inquiry": "inquiry",
}


async def create_card(
    *,
    tenant_id: str,
    conversation_id: str,
    brand: str,
    model: str,
    symptom: str,
    urgency: str,
    category: str | None = None,
    location: str | None = None,
    door_status: str | None = None,
    network_status: str | None = None,
    symptoms: list[str] | None = None,
    intent: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    """建立 ProblemCard。conversation 必須屬同租戶且尚未掛 PC（DB UNIQUE 約束）。

    Mapping：
      - urgency (low/medium/high) → DB low/normal/high
      - symptom (string) ＋ symptoms (string[]) 合併後存入 symptoms JSONB；
        若未提供 symptoms，以「、」拆 symptom 字串
      - intent (unlock_request/repair_request/installation/inquiry) → DB
        repair/repair/other/inquiry
      - status 一律設 'incomplete'（建立時尚未確認，後續走 /confirm 流程）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not brand or not brand.strip():
        raise ApiError("VALIDATION_ERROR", "brand is required", 422)
    if not model or not model.strip():
        raise ApiError("VALIDATION_ERROR", "model is required", 422)
    if not symptom or not symptom.strip():
        raise ApiError("VALIDATION_ERROR", "symptom is required", 422)
    if urgency not in _VALID_API_URGENCY:
        raise ApiError(
            "VALIDATION_ERROR",
            f"urgency must be one of {sorted(_VALID_API_URGENCY)}",
            422,
        )
    if door_status is not None and door_status not in _VALID_DOOR_STATUS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"door_status must be one of {sorted(_VALID_DOOR_STATUS)}",
            422,
        )
    if network_status is not None and network_status not in _VALID_NETWORK_STATUS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"network_status must be one of {sorted(_VALID_NETWORK_STATUS)}",
            422,
        )
    if intent is not None and intent not in _API_INTENT_TO_DB:
        raise ApiError(
            "VALIDATION_ERROR",
            f"intent must be one of {sorted(_API_INTENT_TO_DB)}",
            422,
        )

    # tenant guard via conversations.user.tenant_id
    cur = await db_module._conn.execute(
        "SELECT c.id FROM conversations c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
        (conversation_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError(
            "NOT_FOUND",
            f"Conversation {conversation_id} not found",
            404,
        )

    # PC 表 conversation_id 為 UNIQUE：若已存在 PC，回 409
    cur = await db_module._conn.execute(
        "SELECT id FROM problem_cards WHERE conversation_id = %s::uuid",
        (conversation_id,),
    )
    if await cur.fetchone():
        raise ApiError(
            "STATE_CONFLICT",
            "Problem card already exists for this conversation",
            409,
        )

    # 合併 symptom 字串與 symptoms 陣列
    merged_symptoms: list[str] = []
    if symptoms:
        merged_symptoms.extend(s.strip() for s in symptoms if s and s.strip())
    parsed = [s.strip() for s in symptom.split("、") if s.strip()]
    for p in parsed:
        if p not in merged_symptoms:
            merged_symptoms.append(p)
    if not merged_symptoms:
        merged_symptoms = [symptom.strip()]

    db_urgency = _API_URGENCY_TO_DB[urgency]
    db_intent = _API_INTENT_TO_DB[intent] if intent else None
    media = media_urls if media_urls else None

    cur = await db_module._conn.execute(
        f"INSERT INTO problem_cards "
        f"  (conversation_id, brand, model, category, location, "
        f"   door_status, network_status, symptoms, urgency, intent, "
        f"   media_urls, status) "
        f"VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 'incomplete') "
        f"RETURNING id",
        (
            conversation_id,
            brand.strip()[:100],
            model.strip()[:100],
            (category or "").strip()[:100] or None,
            (location or "").strip()[:255] or None,
            door_status,
            network_status,
            json.dumps(merged_symptoms),
            db_urgency,
            db_intent,
            json.dumps(media) if media else None,
        ),
    )
    row = await cur.fetchone()
    new_id = str(row[0])
    return await get_card(tenant_id=tenant_id, pc_id=new_id)


async def update_card(
    *,
    tenant_id: str,
    pc_id: str,
    brand: str | None = None,
    model: str | None = None,
    symptom: str | None = None,
    category: str | None = None,
    urgency: str | None = None,
    status: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    """部分更新問題卡欄位。status 變更走 /confirm 或 /resolve，PATCH 拒收 status。

    - brand/model/category 直通並 trim 至 schema 上限（DB 欄位 100 字）
    - symptom (string) 以「、」拆回 JSONB 陣列存入 symptoms 欄位
    - urgency (low/medium/high) 反向 mapping 為 DB low/normal/high
    - media_urls list[str] → JSONB array
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if status is not None:
        raise ApiError(
            "VALIDATION_ERROR",
            "status changes must go through /confirm or /resolve endpoints",
            422,
        )

    cur = await db_module._conn.execute(
        "SELECT pc.id "
        "FROM problem_cards pc "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND u.tenant_id = %s::uuid",
        (pc_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Problem card not found", 404)

    sets: list[str] = []
    args: list = []

    if brand is not None:
        sets.append("brand = %s")
        args.append(brand[:100])
    if model is not None:
        sets.append("model = %s")
        args.append(model[:100])
    if symptom is not None:
        symptoms_list = [s.strip() for s in symptom.split("、") if s.strip()]
        sets.append("symptoms = %s::jsonb")
        args.append(json.dumps(symptoms_list))
    if category is not None:
        sets.append("category = %s")
        args.append(category[:100])
    if urgency is not None:
        if urgency not in _VALID_API_URGENCY:
            raise ApiError(
                "VALIDATION_ERROR",
                f"urgency must be one of {sorted(_VALID_API_URGENCY)}",
                422,
            )
        sets.append("urgency = %s")
        args.append(_API_URGENCY_TO_DB[urgency])
    if media_urls is not None:
        sets.append("media_urls = %s::jsonb")
        args.append(json.dumps(media_urls))

    if not sets:
        return await get_card(tenant_id=tenant_id, pc_id=pc_id)

    sets.append("updated_at = NOW()")
    sql = f"UPDATE problem_cards SET {', '.join(sets)} WHERE id = %s::uuid"
    args.append(pc_id)
    await db_module._conn.execute(sql, args)
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)
