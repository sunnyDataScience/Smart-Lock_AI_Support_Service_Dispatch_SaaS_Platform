"""兩層分類器：metadata 快篩 + LLM 語意分類。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from pipeline.silver_to_skill._prompts import CLASSIFY_SYSTEM, CLASSIFY_PROMPT
from pipeline.silver_to_skill._schemas import CLASSIFY_SCHEMA
from pipeline.silver_to_skill._skill_registry import SkillInfo

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]


@dataclass
class Classification:
    source_file: str
    chunk_index: int
    skill_name: str
    confidence: float
    method: str  # "keyword" | "llm"
    reasoning: str


# ── Tier 1：metadata + 關鍵字快篩 ──

# category → skill 預設對應
_CATEGORY_MAP: dict[str, str] = {
    "knowledge": "product-knowledge",
    "specification": "product-knowledge",
}

# troubleshoot 子分類關鍵字
_TS_KEYWORDS: dict[str, list[str]] = {
    "ts-alarm": ["警報", "嗶嗶", "叫", "鳴叫", "蜂鳴", "報警"],
    "ts-door-stuck": ["卡住", "打不開", "被鎖", "鎖住", "推不動", "拉不開", "卡死"],
    "ts-auto-lock": ["自動上鎖", "自動鎖", "馬達空轉", "沒有自動"],
    "ts-lock-tongue": ["鎖舌", "受口片", "鎖栓", "斜舌", "方舌"],
    "ts-door-rebound": ["反弓", "門彈開", "彈回", "門縫", "密合"],
    "ts-power-drain": ["耗電", "沒電", "電池", "電量", "充電", "電力"],
    "ts-verification": ["指紋", "密碼失敗", "驗證", "辨識", "閃6", "NFC", "感應不到"],
    "ts-dual-auth": ["雙重認證", "兩次", "雙重驗證", "二次認證"],
}

# app 子分類關鍵字
_APP_KEYWORDS: dict[str, list[str]] = {
    "app-pairing": ["配對", "WiFi", "藍牙", "連線", "新增裝置", "綁定", "APP連線"],
    "app-remote": ["遠端", "遠程", "遠距", "遠端開鎖", "遠端金鑰"],
    "app-temp-pwd": ["臨時密碼", "暫時密碼", "一次性密碼", "temporary"],
    "app-camera": ["攝影", "鏡頭", "影像", "即時影像", "錄影", "貓眼"],
    "app-family": ["家庭", "家人", "成員管理", "家庭群組"],
    "app-unbind": ["解綁", "解除綁定", "換手機", "移除裝置"],
    "app-user-mgmt": [
        "使用者管理", "指紋管理", "密碼管理", "人臉", "掌紋", "門卡",
        "指紋設定", "密碼設定", "卡片設定", "遙控器設定", "管理者密碼",
        "使用者密碼", "指紋註冊", "卡片註冊", "刪除指紋", "刪除卡片",
        "掌靜脈", "人臉辨識", "RFID",
    ],
    "app-settings": [
        "設定", "音量", "語言", "音效", "語音",
        "常開模式", "兒童安全鎖", "恢復出廠", "出廠設定",
        "音量調整", "語言設定",
    ],
    "app-battery": ["電池", "充電", "電量顯示", "低電量", "行動電源供電", "9V", "緊急供電"],
    "app-voice-msg": ["語音留言", "留言", "語音訊息"],
    "app-cache": ["快取", "清除", "cache", "暫存"],
    "app-guide": [
        "操作教學", "功能操作", "操作設定", "功能介紹",
        "鑰匙解鎖", "鑰匙開門", "機械鑰匙", "安裝教學",
    ],
}


def _keyword_match(content: str, keyword_map: dict[str, list[str]]) -> tuple[str, float] | None:
    """嘗試用關鍵字比對，回傳 (skill_name, confidence) 或 None。

    要求至少命中 2 個關鍵字才視為有效分類，避免「順帶提及」的 chunk 被誤分類。
    """
    scores: dict[str, int] = {}
    for skill, keywords in keyword_map.items():
        count = sum(1 for kw in keywords if kw in content)
        if count > 0:
            scores[skill] = count

    if not scores:
        return None

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] < 2:
        return None
    confidence = min(0.6 + scores[best] * 0.1, 0.95)
    return best, confidence


def classify_tier1(doc: dict, chunk_index: int) -> Classification | None:
    """Tier 1 分類：metadata + 關鍵字，快速且免 LLM。"""
    content = doc.get("content", "")
    source_file = doc.get("_source_file", doc.get("source", "unknown"))
    category = doc.get("category", "")

    # 直接 category 對應
    if category in _CATEGORY_MAP:
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name=_CATEGORY_MAP[category],
            confidence=0.85,
            method="keyword",
            reasoning=f"category={category}",
        )

    # troubleshoot 子分類
    if category == "troubleshoot":
        result = _keyword_match(content, _TS_KEYWORDS)
        if result:
            return Classification(
                source_file=source_file,
                chunk_index=chunk_index,
                skill_name=result[0],
                confidence=result[1],
                method="keyword",
                reasoning=f"category=troubleshoot, keyword match",
            )
        # 有 category 但無法細分 → 歸到 troubleshoot 母技能
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name="troubleshoot",
            confidence=0.7,
            method="keyword",
            reasoning="category=troubleshoot, no sub-skill keyword match",
        )

    # setup 子分類
    if category == "setup":
        result = _keyword_match(content, _APP_KEYWORDS)
        if result:
            return Classification(
                source_file=source_file,
                chunk_index=chunk_index,
                skill_name=result[0],
                confidence=result[1],
                method="keyword",
                reasoning=f"category=setup, keyword match",
            )
        # 有 category 但無法細分 → 歸到 app-guide 母技能
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name="app-guide",
            confidence=0.7,
            method="keyword",
            reasoning="category=setup, no sub-skill keyword match",
        )

    # 無 category 但內容有明顯關鍵字
    all_keywords = {**_TS_KEYWORDS, **_APP_KEYWORDS}
    result = _keyword_match(content, all_keywords)
    if result and result[1] >= 0.7:
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name=result[0],
            confidence=result[1] - 0.1,  # 沒有 category 佐證，降低信心
            method="keyword",
            reasoning="no category, keyword match only",
        )

    # dispatch / store 特殊關鍵字
    dispatch_kw = ["派工", "安裝", "到府", "師傅", "維修"]
    if any(kw in content for kw in dispatch_kw):
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name="dispatch-guide",
            confidence=0.7,
            method="keyword",
            reasoning="dispatch keywords found",
        )

    store_kw = ["門市", "營業", "地址", "電話", "服務據點"]
    if any(kw in content for kw in store_kw):
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name="store-info",
            confidence=0.7,
            method="keyword",
            reasoning="store-info keywords found",
        )

    return None  # 需要 Tier 2 LLM 分類


def classify_tier2(
    doc: dict,
    chunk_index: int,
    skill_list_prompt: str,
    generate_json: Callable,
) -> Classification:
    """Tier 2 分類：LLM 語意分類。"""
    content = doc.get("content", "")
    source_file = doc.get("_source_file", doc.get("source", "unknown"))

    prompt = CLASSIFY_PROMPT.format(
        skill_list=skill_list_prompt,
        document_content=content[:2000],  # 截斷避免 token 過多
    )

    for attempt in range(MAX_RETRIES):
        try:
            result = generate_json(prompt, CLASSIFY_SYSTEM, CLASSIFY_SCHEMA)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  [RETRY {attempt + 1}/{MAX_RETRIES}] classify: {e} (wait {wait}s)")
                time.sleep(wait)
            else:
                print(f"  [FAILED] classify: {e}")
                return Classification(
                    source_file=source_file,
                    chunk_index=chunk_index,
                    skill_name="UNCLASSIFIED",
                    confidence=0.0,
                    method="llm",
                    reasoning=f"LLM failed: {e}",
                )

    skill_name = result.get("skill_name", "UNCLASSIFIED")
    confidence = result.get("confidence", 0.0)
    reasoning = result.get("reasoning", "")

    # confidence 過低視為未分類
    if confidence < 0.5:
        skill_name = "UNCLASSIFIED"

    return Classification(
        source_file=source_file,
        chunk_index=chunk_index,
        skill_name=skill_name,
        confidence=confidence,
        method="llm",
        reasoning=reasoning,
    )
