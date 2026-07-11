"""提煉分流器 — 卡 spine + 對話逐字稿 → 兩軌 draft(ADR-018 步驟②/CR-0139)。

分流規則:
  事實軌 case_entry(必產):症狀→解法的案例史素材,目標落點=案例語料(2.3.2 Publisher 灌)
  行為軌 behavior(選產):對話展現的可重用客服 SOP 模式,目標落點=locksmith-cs-sop skill
    (references/skill 鎖定中——本層只產 draft,寫入屬 2.3.2 且需業主解鎖,CIA §8-3)

不得編造:LLM 只能整理卡欄位與逐字稿既有資訊;provenance 記全程溯源。
冪等:draft_key = sha256(card_id + draft_type + 正規化 payload)[:16]。
"""

import hashlib
import json
from typing import Any

from .llm import GenerateJson

# LLM 輸出 schema(litellm JSON schema 強制;fake 注入時亦依此驗)
REFINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_entry": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "symptom": {"type": "string"},
                "resolution": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["title", "symptom", "resolution", "confidence"],
        },
        "behavior_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "proposal": {"type": "string"},
                    "target_skill": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["title", "proposal", "target_skill", "rationale", "confidence"],
            },
        },
    },
    "required": ["case_entry", "behavior_candidates"],
}

SYSTEM_PROMPT = """你是智慧鎖客服知識的資深編輯。輸入是一張已結案、知識閘(Gate②)已過的問題卡
(含失效分析 spine:根因/矯正措施/驗證/處置)與其完整客服對話逐字稿。

任務——把素材提煉為兩類知識草稿:
1. case_entry(必產一則):案例史。symptom=客戶視角的症狀描述(含品牌型號脈絡);
   resolution=技術視角的解法(整合根因、矯正措施、驗證方式)。文字完整可獨立閱讀。
2. behavior_candidates(0 到 2 則):僅當對話展現「可重用的客服處理模式」
   (如特定情境的問法順序、轉接時機、安全拒答姿態)才產;target_skill 固定 "locksmith-cs-sop"。

鐵律:
- 只能整理輸入中既有的資訊,不得推測或編造未出現的事實
- 使用繁體中文;品牌/型號/術語保持原文
- confidence 為 0-1,反映素材完整度與可重用性"""

_DRAFT_KEY_NS = "kd\x00"


def draft_key(card_id: str, draft_type: str, payload: dict) -> str:
    """確定性 draft id(冪等;比照 knowledge-pipeline chunk_id 慣例)。"""
    canon = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw = f"{_DRAFT_KEY_NS}{card_id}\x00{draft_type}\x00{canon}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _spine_snapshot(card: dict) -> dict:
    keys = ("symptoms", "failure_mode", "triage_tier", "resolution_channel",
            "root_cause", "root_cause_category", "corrective_action",
            "verification", "disposition", "firmware_version", "serial")
    return {k: card.get(k) for k in keys if card.get(k) is not None}


def _build_prompt(card: dict, transcript: list[dict]) -> str:
    lines = [f"[{m['sender_role']}] {m['content']}" for m in transcript]
    return (
        "## 問題卡\n"
        + json.dumps(_spine_snapshot(card) | {
            "brand": card.get("brand"), "model": card.get("model"),
            "category": card.get("category"),
        }, ensure_ascii=False, indent=1)
        + "\n\n## 對話逐字稿\n"
        + ("\n".join(lines) if lines else "(無文字訊息)")
    )


def refine_card(
    card: dict,
    transcript: list[dict],
    *,
    generate: GenerateJson,
    llm_model: str = "",
    refined_at: str = "",
) -> list[dict]:
    """產 draft 列(尚未落庫)。generate 可注入(測試 fake / 生產 llm.generate_json)。"""
    result = generate(_build_prompt(card, transcript), SYSTEM_PROMPT, REFINE_SCHEMA)

    provenance = {
        "problem_card_id": card["id"],
        "conversation_id": card.get("conversation_id"),
        "message_count": len(transcript),
        "spine": _spine_snapshot(card),
        "llm_model": llm_model,
        "refined_at": refined_at,
    }

    drafts: list[dict] = []

    ce = result["case_entry"]
    ce_payload = {"symptom": ce["symptom"], "resolution": ce["resolution"]}
    drafts.append({
        "draft_key": draft_key(card["id"], "case_entry", ce_payload),
        "draft_type": "case_entry",
        "source_problem_card_id": card["id"],
        "source_conversation_id": card.get("conversation_id"),
        "brand": card.get("brand"),
        "model": card.get("model"),
        "category": card.get("category"),
        "title": ce["title"],
        "payload": ce_payload,
        "provenance": provenance,
        "confidence": float(ce["confidence"]),
    })

    for bc in result.get("behavior_candidates", []):
        bc_payload = {
            "proposal": bc["proposal"],
            "target_skill": bc["target_skill"],
            "rationale": bc["rationale"],
        }
        drafts.append({
            "draft_key": draft_key(card["id"], "behavior", bc_payload),
            "draft_type": "behavior",
            "source_problem_card_id": card["id"],
            "source_conversation_id": card.get("conversation_id"),
            "brand": card.get("brand"),
            "model": card.get("model"),
            "category": card.get("category"),
            "title": bc["title"],
            "payload": bc_payload,
            "provenance": provenance,
            "confidence": float(bc["confidence"]),
        })

    return drafts
