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
import hashlib
import io
import json
import logging
import re

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.problem_card_service")


def compute_pc_idempotency_key(
    conv_id: str, first_symptom: str | None, brand: str | None
) -> str:
    """TI-M03-06 / A06：sha256(conv_id + first_unresolved_symptom + brand) 冪等鍵。

    用於 24h dedup 視窗 —— 同一邏輯 turn 經 DLQ/outbox retry 重送時，產生相同鍵，
    避免重複建卡。brand/symptom 缺漏以空字串穩定化（AI 草擬卡常缺 brand）。
    """
    raw = f"{conv_id}|{(first_symptom or '').strip()}|{(brand or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        # UAT P1-1:手建卡無對話 → None(str(None) 會變 'None' 字串炸 response model)
        "conversation_id": str(row[1]) if row[1] is not None else None,
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
        # CR-0128：急件 carve-out 四類（None=非急件）
        "emergency_class": row[13] if len(row) > 13 else None,
        # CR-0132 雙 gate（15_SDS §4.6）
        "intake_completeness": row[14] if len(row) > 14 else None,
        "resolution_completeness": row[15] if len(row) > 15 else None,
        "triage_tier": row[16] if len(row) > 16 else None,
        "resolution_channel": row[17] if len(row) > 17 else None,
        "knowledge_ready": bool(row[18]) if len(row) > 18 and row[18] is not None else False,
        "contact_phone": row[19] if len(row) > 19 else None,
        "failure_mode": row[20] if len(row) > 20 else None,
        "root_cause": row[21] if len(row) > 21 else None,
        "root_cause_category": row[22] if len(row) > 22 else None,
        "corrective_action": row[23] if len(row) > 23 else None,
        "verification": row[24] if len(row) > 24 else None,
        "disposition": row[25] if len(row) > 25 else None,
        "firmware_version": row[26] if len(row) > 26 else None,
        "serial": row[27] if len(row) > 27 else None,
        "resolved_by": str(row[28]) if len(row) > 28 and row[28] else None,
        # UAT P2-8：location 欄位早已落庫（create 有收），但 get/list 一直沒回
        "location": row[29] if len(row) > 29 else None,
        # CR-0178 UAT-0720-09 續：客戶姓名（extracted_fields.customer_name；開單 ConvertModal 預填用）
        "customer_name": row[30] if len(row) > 30 else None,
    }


_PC_SELECT = (
    "pc.id, pc.conversation_id, pc.brand, pc.model, pc.symptoms, pc.category, "
    "pc.urgency, pc.status, pc.media_urls, pc.created_at, pc.updated_at, "
    "pc.source, pc.ai_missing_fields, pc.emergency_class, "
    # CR-0132 雙 gate 欄位
    "pc.intake_completeness, pc.resolution_completeness, pc.triage_tier, "
    "pc.resolution_channel, pc.knowledge_ready, pc.contact_phone, pc.failure_mode, "
    "pc.root_cause, pc.root_cause_category, pc.corrective_action, pc.verification, "
    "pc.disposition, pc.firmware_version, pc.serial, pc.resolved_by, "
    # UAT P2-8（index 29，append-only 保既有索引不變）：服務地址
    "pc.location, "
    # CR-0178 UAT-0720-09 續（index 30，append-only）：客戶姓名（手建卡落 extracted_fields.customer_name）
    "pc.extracted_fields->>'customer_name'"
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

    where = ["COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid"]
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
        f"LEFT JOIN conversations c ON pc.conversation_id = c.id "
        f"LEFT JOIN users u ON c.user_id = u.id "
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
        f"LEFT JOIN conversations c ON pc.conversation_id = c.id "
        f"LEFT JOIN users u ON c.user_id = u.id "
        f"WHERE pc.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid",
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
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid",
        (pc_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)
    return row[0]


async def confirm_card(*, tenant_id: str, pc_id: str) -> dict:
    """incomplete → confirmed。對齊 OpenAPI draft → confirmed。

    CR-0132 Gate①（進料閘，15_SDS §4.6）：M18 config `problemcard_policy.gate1_enforce`
    開啟時，confirm 前必過 §4.6 必填集（contact_phone/brand/model/failure_mode/
    triage_tier＋L3 location）——未過 → 422 INTAKE_GATE_UNMET。預設 off（沿用
    CR-0042 convert 閘行為）；前端補齊分流欄位 UI 上線後由業主開啟。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(pc_id, tenant_id)
    if current not in _CONFIRM_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm problem card in status '{current}'; expected 'incomplete'",
            409,
        )
    await _recompute_gates(pc_id)

    from services import config_m18_service
    cfg = await config_m18_service.read_global_value(namespace="problemcard_policy")
    if isinstance(cfg, dict) and cfg.get("gate1_enforce"):
        cur = await db_module._conn.execute(
            "SELECT contact_phone, brand, model, failure_mode, triage_tier, location "
            "FROM problem_cards WHERE id = %s::uuid", (pc_id,))
        row = await cur.fetchone()
        keys = ("contact_phone", "brand", "model", "failure_mode", "triage_tier", "location")
        pc = dict(zip(keys, row))
        g1 = list(_GATE1_FIELDS) + (["location"] if pc.get("triage_tier") == "L3" else [])
        missing = [f for f in g1 if not _field_filled(pc.get(f))]
        if missing:
            raise ApiError(
                "INTAKE_GATE_UNMET",
                f"進料閘（Gate①）未過——缺：{', '.join(missing)}（15_SDS §4.6；小編補齊後再確認）",
                422,
                details=[{"field": f, "issue": "missing", "gate": "intake"} for f in missing],
            )

    await db_module._conn.execute(
        "UPDATE problem_cards SET status = 'confirmed', updated_at = NOW() "
        "WHERE id = %s::uuid",
        (pc_id,),
    )
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)


async def resolve_card(
    *, tenant_id: str, pc_id: str, resolution_layer: str,
    resolved_by: str | None = None, resolution_channel: str | None = None,
) -> dict:
    """confirmed → resolved，記錄 resolution_layer (L1/L2/L3)。

    CR-0132：同步落分流欄——triage_tier（空時以 layer 補）、resolution_channel
    （未明給時依 layer 預設映射 L1→ai_auto/L2→line_text_cs/L3→onsite）、
    resolved_by（操作者）；resolve 後重算雙完整度（Gate② 起算）。
    """
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
    if resolution_channel is not None and resolution_channel not in _RESOLUTION_CHANNELS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"resolution_channel must be one of {sorted(_RESOLUTION_CHANNELS)}",
            422,
        )
    await db_module._conn.execute(
        "UPDATE problem_cards SET "
        "  status = 'resolved', "
        "  resolution_layer = %s, "
        # CR-0132：triage_tier 空時以 layer 補；channel 未明給依 layer 預設映射
        "  triage_tier = COALESCE(triage_tier, %s), "
        "  resolution_channel = COALESCE(%s, resolution_channel, %s), "
        "  resolved_by = COALESCE(%s::uuid, resolved_by), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (resolution_layer, resolution_layer,
         resolution_channel, _LAYER_DEFAULT_CHANNEL.get(resolution_layer),
         resolved_by, pc_id),
    )
    await _recompute_gates(pc_id)
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)


async def list_knowledge_queue(*, tenant_id: str, limit: int = 100) -> list[dict]:
    """待補知識佇列（CR-0132 / 15_SDS §4.6）：operational 已結（resolved）但 Gate②
    未過（knowledge_ready=FALSE）的卡——提示小編/技師補 RMA spine；精煉只吃 ready。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        f"SELECT {_PC_SELECT} FROM problem_cards pc "
        "WHERE pc.tenant_id = %s::uuid AND pc.status = 'resolved' AND pc.knowledge_ready = FALSE "
        "ORDER BY pc.updated_at DESC LIMIT %s",
        (tenant_id, limit),
    )
    return [_pc_row_to_dict(r) for r in await cur.fetchall()]


# PATCH 不允許改 status；狀態請走 /confirm 或 /resolve（避免 state machine 被旁路）
_API_URGENCY_TO_DB = {"low": "low", "medium": "normal", "high": "high"}
# CR-0128/ADR-015①：急件 carve-out 四類（跳過報價直接開單、事後補審）
_VALID_EMERGENCY_CLASSES = {"locked_out", "trapped_inside", "safety_risk", "angry_high_risk"}

# ── CR-0132 雙 gate（15_SDS §4.6 / 18_DB §4.3）────────────────────────────────
_TRIAGE_TIERS = {"L1", "L2", "L3"}
_RESOLUTION_CHANNELS = {"ai_auto", "line_text_cs", "phone_callback", "onsite"}
_DISPOSITIONS = {"replacement", "repair", "software_update", "user_education",
                 "onsite_service", "ntf"}
# resolution_layer → 預設處理管道（resolve 未明給 channel 時的映射）
_LAYER_DEFAULT_CHANNEL = {"L1": "ai_auto", "L2": "line_text_cs", "L3": "onsite"}

# Gate①（進料/派工）必填；triage_tier=L3 時追加 location（服務地址，既有 HITL 補址欄）
_GATE1_FIELDS = ("contact_phone", "brand", "model", "failure_mode", "triage_tier")
# Gate②（知識/精煉 RMA spine）必填；L3 追加 firmware_version/serial
_GATE2_FIELDS = ("root_cause", "root_cause_category", "corrective_action",
                 "verification", "disposition", "resolution_channel", "resolved_by")


def _dual_scores(pc: dict) -> tuple[float, float]:
    """依 §4.6 必填集計算 (intake_completeness, resolution_completeness)。"""
    tier = pc.get("triage_tier")
    g1 = list(_GATE1_FIELDS) + (["location"] if tier == "L3" else [])
    g2 = list(_GATE2_FIELDS) + (["firmware_version", "serial"] if tier == "L3" else [])
    def score(fields):
        filled = sum(1 for f in fields if _field_filled(pc.get(f)))
        return round(filled / max(len(fields), 1), 2)
    return score(g1), score(g2)


async def _recompute_gates(pc_id: str) -> None:
    """重算雙完整度並持久化；Gate② 滿分 → knowledge_ready=TRUE（精煉汲取條件）。

    knowledge_ready 單向落 TRUE 後不自動退回（避免精煉已汲取後旗標翻覆）；
    spine 欄位被清空屬人工異常，交由審核流程處理。
    """
    cur = await db_module._conn.execute(
        "SELECT contact_phone, brand, model, failure_mode, triage_tier, location, "
        "       root_cause, root_cause_category, corrective_action, verification, "
        "       disposition, resolution_channel, resolved_by, firmware_version, serial "
        "FROM problem_cards WHERE id = %s::uuid",
        (pc_id,),
    )
    row = await cur.fetchone()
    if not row:
        return
    keys = ("contact_phone", "brand", "model", "failure_mode", "triage_tier", "location",
            "root_cause", "root_cause_category", "corrective_action", "verification",
            "disposition", "resolution_channel", "resolved_by", "firmware_version", "serial")
    pc = dict(zip(keys, row))
    intake, resolution = _dual_scores(pc)
    await db_module._conn.execute(
        "UPDATE problem_cards SET intake_completeness = %s, resolution_completeness = %s, "
        "  knowledge_ready = (knowledge_ready OR %s), updated_at = updated_at "
        "WHERE id = %s::uuid",
        (intake, resolution, resolution >= 1.0, pc_id),
    )
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


# ── CR-0042 ProblemCard 完整度 gate（BR-M03，業主裁決 0.8 硬擋+主管 override；門檻入 M18 config）──
_COMPLETENESS_DEFAULTS = {
    "min_completeness": 0.8,
    "key_fields": ["brand", "model", "symptom", "urgency", "customer_address"],
}
_COMPLETENESS_OVERRIDE_ROLES = {"admin", "operations_manager"}

# CR-0057 / Q015 / BR-M05-03：ProblemCard 三級必填分類落地（CR-0026 §8 裁決的三層）。
#   required      = 建卡即必填（缺則 PC 不成立）
#   pre_dispatch  = 派工前必填（缺則不可轉 WO/派工，對齊 work_order _DISPATCH_REQUIRED）
#   optional      = 可後補（不擋流程，現場/事後補齊）
_PC_FIELD_TIERS = {
    "required": ["brand", "model", "symptom", "urgency"],
    "pre_dispatch": ["customer_address", "problem_type"],
    "optional": ["serial_number", "door_type", "door_status", "network_status"],
}


def _field_tier(field: str) -> str:
    """欄位所屬必填層（required/pre_dispatch/optional）；未分類視為 optional。"""
    for tier, fields in _PC_FIELD_TIERS.items():
        if field in fields:
            return tier
    return "optional"


def required_field_tiers() -> dict:
    """對外揭露三級必填分類定義（前端/agent 可據此標示欄位層級）。"""
    return {k: list(v) for k, v in _PC_FIELD_TIERS.items()}


def _field_filled(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    return True


async def assert_completeness(
    *,
    tenant_id: str,
    pc_id: str,
    customer_address: str | None = None,
    actor_role: str | None = None,
    override_reason: str | None = None,
) -> dict:
    """CR-0042：轉 WO 前檢查 ProblemCard 完整度達門檻，否則 422（主管帶 reason 可 override）。

    完整度 = 已填 key 欄 / key 欄總數；門檻讀 M18 config problemcard_policy（缺則 fallback 0.8）。
    回 {score, missing, threshold, overridden}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    from services import config_m18_service

    policy = dict(_COMPLETENESS_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="problemcard_policy")
    if isinstance(cfg, dict):
        policy.update(cfg)
    key_fields = policy.get("key_fields") or _COMPLETENESS_DEFAULTS["key_fields"]
    min_c = float(policy.get("min_completeness", 0.8))

    # CR-0165 F6b：LEFT JOIN 取 user profile 地址——閘門 fallback 與下游建單
    # create_from_problem_card 的 `customer_address or user_address` 完全鏡射，
    # 避免「閘門 422 擋掉一筆實際建單能成功的轉換」。
    cur = await db_module._conn.execute(
        "SELECT pc.brand, pc.model, pc.symptoms, pc.symptom_summary, pc.urgency, "
        "       u.address "
        "FROM problem_cards pc "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid",
        (pc_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)
    symptom_ok = _field_filled(row[2]) or _field_filled(row[3])
    values = {
        "brand": row[0],
        "model": row[1],
        "symptom": "x" if symptom_ok else None,
        "urgency": row[4],
        "customer_address": customer_address or row[5],
    }
    missing = [f for f in key_fields if not _field_filled(values.get(f))]
    score = round((len(key_fields) - len(missing)) / max(len(key_fields), 1), 2)

    overridden = bool(
        override_reason
        and override_reason.strip()
        and (actor_role or "").lower() in _COMPLETENESS_OVERRIDE_ROLES
    )
    if score < min_c and not overridden:
        raise ApiError(
            "INCOMPLETE_PROBLEM_CARD",
            f"問題卡完整度 {score} < {min_c}（缺：{', '.join(missing) or '—'}）；補齊欄位或主管 override",
            422,
            # CR-0052 結構化 + CR-0057 三級必填分層（前端可依 tier 標示緊急度）
            details=[{"field": f, "issue": "missing", "tier": _field_tier(f)} for f in missing],
        )
    return {
        "score": score, "missing": missing, "threshold": min_c, "overridden": overridden,
        # CR-0057：缺漏欄位依三級分層（required/pre_dispatch/optional）
        "missing_by_tier": {
            tier: [f for f in missing if _field_tier(f) == tier]
            for tier in ("required", "pre_dispatch", "optional")
        },
    }


async def create_card(
    *,
    tenant_id: str,
    conversation_id: str | None,
    brand: str | None,
    model: str | None,
    symptom: str,
    urgency: str,
    category: str | None = None,
    location: str | None = None,
    door_status: str | None = None,
    network_status: str | None = None,
    symptoms: list[str] | None = None,
    intent: str | None = None,
    media_urls: list[str] | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> dict:
    """建立 ProblemCard。conversation 必須屬同租戶且尚未掛 PC（DB UNIQUE 約束）。

    UAT P1-1：conversation_id 可為 None＝客服手建卡（電話進線，無 LINE 對話；
    DB 欄本就 nullable、source default 'human'）。此時跳過 conversation guard
    與 active-card 檢查；customer_phone 落 contact_phone 欄、customer_name 落
    extracted_fields.customer_name（轉工單 fallback 帶出）。

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

    # UAT P1-1:brand/model 改選填(電話報修常不知型號;與 AI 草擬卡同等寬鬆,
    # 缺欄由完整度 gate/待補機制補齊。DB 欄 nullable)
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

    # tenant guard via conversations.user.tenant_id（手建卡無對話 → 跳過）
    if conversation_id is not None:
        cur = await db_module._conn.execute(
            "SELECT c.id FROM conversations c "
            "LEFT JOIN users u ON c.user_id = u.id "
            "WHERE c.id = %s::uuid AND u.tenant_id = %s::uuid",
            (conversation_id, tenant_id),
        )
        if not await cur.fetchone():
            raise ApiError(
                "NOT_FOUND",
                f"Conversation {conversation_id} not found",
                404,
            )

        # CR-0096：同一 conversation 同時只能有一張「仍 active」的卡（部分唯一索引）。
        # 已轉工單/結案的舊卡不算 → 同一客人可再開新卡。撞 active 卡才回 409。
        cur = await db_module._conn.execute(
            "SELECT id FROM problem_cards "
            "WHERE conversation_id = %s::uuid "
            "  AND status NOT IN ('resolved', 'escalated') AND converted_at IS NULL",
            (conversation_id,),
        )
        if await cur.fetchone():
            raise ApiError(
                "STATE_CONFLICT",
                "An active problem card already exists for this conversation",
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

    # UAT P1-1：手建卡客戶資訊——電話落 contact_phone、姓名落 extracted_fields
    extracted = (
        json.dumps({"customer_name": customer_name.strip()[:100]})
        if customer_name and customer_name.strip()
        else None
    )
    cur = await db_module._conn.execute(
        f"INSERT INTO problem_cards "
        f"  (conversation_id, brand, model, category, location, "
        f"   door_status, network_status, symptoms, urgency, intent, "
        f"   media_urls, status, tenant_id, contact_phone, extracted_fields) "
        f"VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 'incomplete', %s::uuid, %s, %s::jsonb) "
        f"RETURNING id",
        (
            conversation_id,
            (brand or "").strip()[:100] or None,
            (model or "").strip()[:100] or None,
            (category or "").strip()[:100] or None,
            (location or "").strip()[:255] or None,
            door_status,
            network_status,
            json.dumps(merged_symptoms),
            db_urgency,
            db_intent,
            json.dumps(media) if media else None,
            tenant_id,  # CR-0132：直接租戶欄
            (customer_phone or "").strip()[:20] or None,
            extracted,
        ),
    )
    row = await cur.fetchone()
    new_id = str(row[0])
    await _recompute_gates(new_id)
    return await get_card(tenant_id=tenant_id, pc_id=new_id)


# CR-0022/ADR-0112：AI 草擬卡預設待補欄位（客服在佇列補全；location 為 convert 前置硬需求）
_AI_DRAFT_MISSING_FIELDS = ["brand", "model", "location"]


# CR-0102：台灣手機正規化（API 端防禦驗證；agent 已抽好，這裡再驗一次才寫 users）。
# 只認手機 09xxxxxxxx（容 +886 與分隔符）；非手機回空字串，不寫入。
_TW_MOBILE_RE = re.compile(r"^09\d{8}$")


def _normalize_tw_mobile(raw: str | None) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("886"):  # +886 9... → 09...
        digits = "0" + digits[3:]
    return digits if _TW_MOBILE_RE.match(digits) else ""


async def _ensure_line_case(*, tenant_id: str, conv_id: str, pc_id: str, summary: str) -> None:
    """CR-0108 S3：LINE 進線問題卡 ensure 一張 source_channel=line 的 Case 並連 case_id。

    讓 LINE 進線也收斂到 M01 Case 模型（與電話/官網/熟客介紹手動建案一致）。
    一卡一 Case（已連 case_id 則略過，冪等）。客戶資訊取自對話 user（D6：phone+LINE ID）。
    **best-effort**：Case 建立失敗不阻斷建卡主流程（比照 CR-0102 電話回填）。
    """
    try:
        cur = await db_module._conn.execute(
            "SELECT case_id FROM problem_cards WHERE id = %s::uuid", (pc_id,))
        row = await cur.fetchone()
        if row and row[0]:
            return  # 已連 Case

        cur = await db_module._conn.execute(
            "SELECT u.id, u.display_name, u.phone, u.line_user_id "
            "FROM conversations c LEFT JOIN users u ON c.user_id = u.id "
            "WHERE c.id = %s::uuid", (conv_id,))
        urow = await cur.fetchone()
        from services import intake_case_service  # 避免模組級循環 import

        # UAT-0718 W5-4：回填 conversation_id + problem_card_id（migration 108）
        # ——案件不再是資訊孤島，前端可從案件跳回來源對話與問題卡。
        result = await intake_case_service.create_case(
            tenant_id=tenant_id,
            source_channel="line",
            summary=(summary or "")[:500] or None,
            customer_name=urow[1] if urow else None,
            customer_phone=urow[2] if urow else None,
            customer_line_id=urow[3] if urow else None,
            customer_id=str(urow[0]) if urow and urow[0] else None,
            created_by=None,
            conversation_id=conv_id,
            problem_card_id=pc_id,
        )
        case_id = result["data"]["id"]
        await db_module._conn.execute(
            "UPDATE problem_cards SET case_id = %s::uuid WHERE id = %s::uuid AND case_id IS NULL",
            (case_id, pc_id))
    except Exception:  # noqa: BLE001 — ensure Case 失敗不可阻斷建卡主流程
        logger.warning("CR-0108 S3 ensure LINE case 失敗（已略過）", exc_info=True)


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
    # CR-0098：LLM 在 transfer_to_human 已從對話抽出的裝置/症狀 → 建卡時自動填，免客服重打。
    ai_brand = (snapshot.get("brand") or "").strip()
    ai_model = (snapshot.get("model") or "").strip()
    ai_symptom = (snapshot.get("symptom") or "").strip()

    # CR-0102：客人在 LINE 留的手機 → 寫進該對話 user 的 users.phone（只在空白時填，不蓋
    # 客服手動值或客人先前提供的號碼）。convert（create_from_problem_card）既有邏輯讀
    # users.phone 帶進 work_orders.customer_phone → 轉工單時客戶電話自動填上（業主需求）。
    # best-effort：寫入失敗不阻斷建卡（電話是加值，建卡是主流程）。
    ai_phone = _normalize_tw_mobile(snapshot.get("phone"))
    if ai_phone:
        try:
            cur = await db_module._conn.execute(
                "UPDATE users SET phone = %s, updated_at = NOW() "
                "WHERE id = (SELECT user_id FROM conversations WHERE id = %s::uuid) "
                "  AND (phone IS NULL OR phone = '') "
                "RETURNING id",
                (ai_phone, conv_id),
            )
            urow = await cur.fetchone()
            if urow:
                # CR-0176 S2：phone dual-write（同 try 內 best-effort，失敗不阻斷建卡）
                from services import dek_service

                await dek_service.dual_write_user_pii(
                    str(urow[0]), None, {"phone": ai_phone}
                )
        except Exception:  # noqa: BLE001 — 電話回填失敗不可阻斷建卡主流程
            logger.warning("CR-0102 回填 users.phone 失敗（已略過）", exc_info=True)
    # 症狀文字優先取 LLM 抽出的精準症狀，其次客人原話摘要，再否則 agent 轉接理由
    symptom_text = (ai_symptom or excerpt or reason or "").strip()[:1000] or "（客人轉真人，詳見對話）"

    # TI-M03-06 / A06：sha256 冪等鍵 + 24h dedup 視窗（抵抗 DLQ/outbox retry 重複建卡）。
    # brand 在 AI 草擬卡多為空，鍵以 conv_id + 症狀 為主。命中 24h 內同鍵 → 回既有（冪等）。
    # CR-0096：只認「仍 active」的卡為 dedup 目標 —— 已轉工單/結案的舊卡不算，
    #          否則客人對已派工的舊問題再提同症狀會被誤 dedup 回舊卡、開不了新卡。
    idem_key = compute_pc_idempotency_key(conv_id, symptom_text, snapshot.get("brand"))
    kcur = await db_module._conn.execute(
        "SELECT id FROM problem_cards "
        "WHERE idempotency_key = %s AND created_at > NOW() - INTERVAL '24 hours' "
        "  AND status NOT IN ('resolved', 'escalated') AND converted_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        (idem_key,),
    )
    krow = await kcur.fetchone()
    if krow:
        pc_id = str(krow[0])
        card = await get_card(tenant_id=tenant_id, pc_id=pc_id)
        return {"problem_card_id": pc_id, "conversation_id": conv_id,
                "created": False, "deduplicated": True, "card": card}

    # CR-0096：只找「仍 active」的卡來併入（未結案 且 未轉工單）。
    # 舊卡已轉工單/結案 → existing 為空 → 落到下方建「新卡」（同一 LINE 客人的新問題獨立成卡）。
    cur = await db_module._conn.execute(
        "SELECT id, symptoms FROM problem_cards "
        "WHERE conversation_id = %s::uuid "
        "  AND status NOT IN ('resolved', 'escalated') AND converted_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
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
            "UPDATE problem_cards SET symptoms = %s::jsonb, updated_at = NOW(), "
            "  idempotency_key = COALESCE(idempotency_key, %s) "
            "WHERE id = %s::uuid",
            (json.dumps(merged, ensure_ascii=False), idem_key, pc_id),
        )
        # CR-0108 S3：併入既有 active 卡時，若該卡尚無 Case（pre-S3 舊卡）則補連一張。
        await _ensure_line_case(tenant_id=tenant_id, conv_id=conv_id, pc_id=pc_id, summary=symptom_text)
        card = await get_card(tenant_id=tenant_id, pc_id=pc_id)
        return {"problem_card_id": pc_id, "conversation_id": conv_id, "created": False, "card": card}

    # CR-0098：LLM 已從對話抽出的 brand/model 自動填入（沒抽到才留空待客服補）；
    # ai_missing_fields 動態剔除已填欄位，前端「待補」徽章才準確。
    filled = {"brand": ai_brand, "model": ai_model}
    missing = [f for f in _AI_DRAFT_MISSING_FIELDS if not filled.get(f)]
    urgency = "high" if is_explicit else "normal"
    cur = await db_module._conn.execute(
        "INSERT INTO problem_cards "
        "  (conversation_id, brand, model, category, symptoms, urgency, intent, status, "
        "   source, ai_missing_fields, idempotency_key, tenant_id) "
        "VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s, 'repair', 'incomplete', "
        "        'ai_line', %s::jsonb, %s, %s::uuid) "
        "RETURNING id",
        (
            conv_id,
            ai_brand or None,
            ai_model or None,
            "其他",
            json.dumps([symptom_text], ensure_ascii=False),
            urgency,
            json.dumps(missing),
            idem_key,
            tenant_id,  # CR-0132：直接租戶欄
        ),
    )
    row = await cur.fetchone()
    pc_id = str(row[0])
    await _recompute_gates(pc_id)
    # CR-0108 S3：新 LINE 進線卡 → ensure 一張 source_channel=line 的 Case 並連 case_id。
    await _ensure_line_case(tenant_id=tenant_id, conv_id=conv_id, pc_id=pc_id, summary=symptom_text)
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
    emergency_class: str | None = None,
    # CR-0132 雙 gate 欄位（15_SDS §4.6：分流＋RMA spine，小編/技師漸進補寫）
    contact_phone: str | None = None,
    failure_mode: str | None = None,
    triage_tier: str | None = None,
    resolution_channel: str | None = None,
    root_cause: str | None = None,
    root_cause_category: str | None = None,
    corrective_action: str | None = None,
    verification: bool | None = None,
    disposition: str | None = None,
    firmware_version: str | None = None,
    serial: str | None = None,
) -> dict:
    """部分更新問題卡欄位。status 變更走 /confirm 或 /resolve，PATCH 拒收 status。

    emergency_class（CR-0128/ADR-015①）：急件 carve-out 四類標記；空字串=清除（回非急件）。

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
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid",
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
    # CR-0132：雙 gate 欄位（enum 驗證＋trim）
    if triage_tier is not None:
        if triage_tier not in _TRIAGE_TIERS:
            raise ApiError("VALIDATION_ERROR", f"triage_tier must be one of {sorted(_TRIAGE_TIERS)}", 422)
        sets.append("triage_tier = %s"); args.append(triage_tier)
    if resolution_channel is not None:
        if resolution_channel not in _RESOLUTION_CHANNELS:
            raise ApiError("VALIDATION_ERROR", f"resolution_channel must be one of {sorted(_RESOLUTION_CHANNELS)}", 422)
        sets.append("resolution_channel = %s"); args.append(resolution_channel)
    if disposition is not None:
        if disposition not in _DISPOSITIONS:
            raise ApiError("VALIDATION_ERROR", f"disposition must be one of {sorted(_DISPOSITIONS)}", 422)
        sets.append("disposition = %s"); args.append(disposition)
    for _col, _val, _lim in (
        ("contact_phone", contact_phone, 50), ("failure_mode", failure_mode, 60),
        ("root_cause_category", root_cause_category, 60),
        ("firmware_version", firmware_version, 50), ("serial", serial, 100),
    ):
        if _val is not None:
            sets.append(f"{_col} = %s"); args.append(_val.strip()[:_lim] or None)
    for _col, _val in (("root_cause", root_cause), ("corrective_action", corrective_action)):
        if _val is not None:
            sets.append(f"{_col} = %s"); args.append(_val.strip() or None)
    if verification is not None:
        sets.append("verification = %s"); args.append(verification)

    if emergency_class is not None:
        if emergency_class == "":
            sets.append("emergency_class = NULL")
        elif emergency_class in _VALID_EMERGENCY_CLASSES:
            sets.append("emergency_class = %s")
            args.append(emergency_class)
        else:
            raise ApiError(
                "VALIDATION_ERROR",
                f"emergency_class must be one of {sorted(_VALID_EMERGENCY_CLASSES)}（或空字串清除）",
                422,
            )
    if media_urls is not None:
        # TI-M03-07：media_urls append-only（Sync-M03）—— 更新不覆蓋既有，採聯集去重保序。
        # 多模態媒體（A08）陸續上傳，覆蓋會掉先前已附的證據照；故讀既有後 append 新者。
        mcur = await db_module._conn.execute(
            "SELECT media_urls FROM problem_cards WHERE id = %s::uuid", (pc_id,)
        )
        mrow = await mcur.fetchone()
        existing_media = mrow[0] if mrow and isinstance(mrow[0], list) else []
        merged_media: list[str] = list(existing_media)
        for u in media_urls:
            if u not in merged_media:
                merged_media.append(u)
        sets.append("media_urls = %s::jsonb")
        args.append(json.dumps(merged_media))

    if not sets:
        return await get_card(tenant_id=tenant_id, pc_id=pc_id)

    sets.append("updated_at = NOW()")
    sql = f"UPDATE problem_cards SET {', '.join(sets)} WHERE id = %s::uuid"
    args.append(pc_id)
    await db_module._conn.execute(sql, args)
    await _recompute_gates(pc_id)  # CR-0132：欄位異動 → 雙完整度重算（Gate② 滿 → knowledge_ready）
    return await get_card(tenant_id=tenant_id, pc_id=pc_id)
