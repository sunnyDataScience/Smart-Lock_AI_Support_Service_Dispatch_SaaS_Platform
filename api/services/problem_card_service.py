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

import base64
import csv
import io
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
        # CR-0022/ADR-0112：來源（human / ai_line）+ AI 草擬待補欄位 hint
        "source": row[11] if len(row) > 11 else "human",
        "ai_missing_fields": (row[12] if len(row) > 12 else None) or None,
    }


_PC_SELECT = (
    "pc.id, pc.conversation_id, pc.brand, pc.model, pc.symptoms, pc.category, "
    "pc.urgency, pc.status, pc.media_urls, pc.created_at, pc.updated_at, "
    "pc.source, pc.ai_missing_fields"
)


async def list_cards(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    conversation_id: str | None = None,
    status: str | None = None,
    urgency: str | None = None,
    brand: str | None = None,
    created_after: str | None = None,
    keyword: str | None = None,
    source: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if conversation_id:
        where.append("pc.conversation_id = %s::uuid")
        args.append(conversation_id)

    if status:
        where.append("pc.status = %s")
        args.append(status)

    # CR-0022：後台「待轉 WO 佇列」依來源篩 AI 草擬卡（source=ai_line）
    if source:
        where.append("pc.source = %s")
        args.append(source)

    if urgency:
        where.append("pc.urgency = %s")
        args.append(urgency)

    if brand:
        where.append("pc.brand = %s")
        args.append(brand)

    if created_after:
        where.append("pc.created_at >= %s::timestamptz")
        args.append(created_after)

    if keyword:
        where.append(
            "(pc.location ILIKE %s OR pc.brand ILIKE %s OR pc.model ILIKE %s)"
        )
        like = f"%{keyword}%"
        args.extend([like, like, like])

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


# CR-0022/ADR-0112：AI 草擬卡預設待補欄位（客服在佇列補全；location 為 convert 前置硬需求）
_AI_DRAFT_MISSING_FIELDS = ["brand", "model", "location"]


async def escalation_to_draft_pc(
    *,
    tenant_id: str,
    line_user_id: str,
    session_id: str,
    reason: str,
    is_explicit: bool = False,
    facts_snapshot: dict | None = None,
    display_name: str | None = None,
) -> dict:
    """LINE agent escalation → AI 草擬問題卡（HITL，CR-0022 / ADR-0112）。

    流程：
      1. ensure conversation（復用 conversation_service.create_conversation，session_id 冪等）
      2. 依 conversation_id（UNIQUE）去重：
         - 已有 PC → 附記 reason 到 symptoms + 更新 ai_missing_fields + updated_at（不重建）
         - 無 → 建 source='ai_line' 草擬卡，status='incomplete'（=API draft），寬鬆（缺
           brand/model 不擋），ai_missing_fields 記待補欄位
      3. 回 {problem_card_id, conversation_id, created}

    **AI 永不自轉工單**：本函式最多建草擬卡；confirm + convert 一律由客服經認證端點觸發
    （ADR-0028 charter / ADR-0031）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    from services import conversation_service  # 避免模組級循環 import

    conv, _ = await conversation_service.create_conversation(
        tenant_id=tenant_id,
        line_user_id=line_user_id,
        session_id=session_id,
        display_name=display_name,
    )
    conv_id = conv["id"]

    # escalation = 進入「等待人工」：把對話翻成 escalated（DB）/ waiting_human（API），
    # 這是 F-018 客服接管發訊（HandoverComposer + send_message）的啟用前提。
    # 無此步驟，AI 雖已草擬問題卡，但對話管理發訊框永遠唯讀（誰都回不了 LINE）。
    # 不限原狀態（含 resolved 後客人再次轉真人）一律 re-escalate；message_count 不變。
    await db_module._conn.execute(
        "UPDATE conversations SET status = 'escalated', updated_at = NOW() "
        "WHERE id = %s::uuid AND status IS DISTINCT FROM 'escalated'",
        (conv_id,),
    )

    snapshot = facts_snapshot or {}
    excerpt = (snapshot.get("user_input_excerpt") or "").strip()
    # 症狀文字優先取客人原話摘要，否則用 agent 轉接理由
    symptom_text = (excerpt or reason or "").strip()[:1000] or "（客人轉真人，詳見對話）"

    # 去重：conversation_id UNIQUE
    cur = await db_module._conn.execute(
        "SELECT id, symptoms FROM problem_cards WHERE conversation_id = %s::uuid",
        (conv_id,),
    )
    existing = await cur.fetchone()

    if existing:
        pc_id = str(existing[0])
        prev = existing[1] if isinstance(existing[1], list) else []
        merged = list(prev)
        if symptom_text not in merged:
            merged.append(symptom_text)
        await db_module._conn.execute(
            "UPDATE problem_cards SET symptoms = %s::jsonb, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (json.dumps(merged, ensure_ascii=False), pc_id),
        )
        card = await get_card(tenant_id=tenant_id, pc_id=pc_id)
        return {"problem_card_id": pc_id, "conversation_id": conv_id, "created": False, "card": card}

    # 新建寬鬆草擬卡（brand/model 留空，待客服補；urgency 依 is_explicit）
    urgency = "high" if is_explicit else "normal"
    cur = await db_module._conn.execute(
        "INSERT INTO problem_cards "
        "  (conversation_id, category, symptoms, urgency, intent, status, "
        "   source, ai_missing_fields) "
        "VALUES (%s::uuid, %s, %s::jsonb, %s, 'repair', 'incomplete', "
        "        'ai_line', %s::jsonb) "
        "RETURNING id",
        (
            conv_id,
            "其他",
            json.dumps([symptom_text], ensure_ascii=False),
            urgency,
            json.dumps(_AI_DRAFT_MISSING_FIELDS),
        ),
    )
    row = await cur.fetchone()
    pc_id = str(row[0])
    card = await get_card(tenant_id=tenant_id, pc_id=pc_id)
    return {"problem_card_id": pc_id, "conversation_id": conv_id, "created": True, "card": card}


_EXPORT_FIELDS = (
    "id", "conversation_id", "brand", "model", "symptom", "category",
    "urgency", "status", "media_urls", "created_at", "updated_at",
)


def _format_card_json(card: dict) -> bytes:
    return json.dumps(card, ensure_ascii=False, indent=2).encode("utf-8")


def _format_card_csv(card: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_EXPORT_FIELDS)
    writer.writerow([
        "" if (v := card.get(f)) is None
        else "; ".join(str(x) for x in v) if isinstance(v, list)
        else str(v)
        for f in _EXPORT_FIELDS
    ])
    return buf.getvalue().encode("utf-8")


def _format_card_pdf(card: dict) -> bytes:
    """簡易純文字 PDF — 不引入 reportlab 依賴；以最小 PDF 1.4 結構嵌入卡片明細。"""
    lines: list[str] = ["Problem Card Export", ""]
    for f in _EXPORT_FIELDS:
        v = card.get(f)
        if v is None:
            v_str = "-"
        elif isinstance(v, list):
            v_str = "; ".join(str(x) for x in v) if v else "-"
        else:
            v_str = str(v)
        # PDF 字串需脫逸括號與反斜線
        safe = v_str.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        lines.append(f"{f}: {safe}")

    text_ops = "\n".join(
        f"({line}) Tj T*" if line else "() Tj T*"
        for line in lines
    )
    content = (
        "BT\n"
        "/F1 11 Tf\n"
        "40 800 Td\n"
        "14 TL\n"
        f"{text_ops}\n"
        "ET"
    )
    content_bytes = content.encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1")
        + content_bytes + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode("latin-1")
    return bytes(out)


async def export_card(*, tenant_id: str, pc_id: str, fmt: str) -> dict:
    """匯出問題卡為 json / csv / pdf；content 以 base64 編碼回傳。"""
    if fmt not in ("json", "csv", "pdf"):
        raise ApiError(
            "VALIDATION_ERROR",
            "format must be one of json, csv, pdf",
            422,
        )

    card = await get_card(tenant_id=tenant_id, pc_id=pc_id)

    if fmt == "json":
        raw = _format_card_json(card)
    elif fmt == "csv":
        raw = _format_card_csv(card)
    else:
        raw = _format_card_pdf(card)

    return {
        "format": fmt,
        "content": base64.b64encode(raw).decode("ascii"),
        "download_url": None,
    }


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
