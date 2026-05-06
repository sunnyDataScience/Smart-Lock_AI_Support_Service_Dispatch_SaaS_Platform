"""兩層分類器：metadata 快篩 + LLM 語意分類。

品牌感知：Tier 1 分類後，依據 silver doc 的 brand 欄位
將基礎技能名（如 ts-alarm）解析為品牌版技能名（如 ts-alarm-dormakaba）。
"""

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


# ── 品牌正規化 ──

_BRAND_ALIASES: dict[str, str] = {
    "chainlock": "Chatlock",
    "chatlock": "Chatlock",
    "dormakaba": "Dormakaba",
    "多瑪": "Dormakaba",
    "philips": "Philips",
    "飛利浦": "Philips",
    "kaadas": "Kaadas",
    "凱迪仕": "Kaadas",
    "milre": "Milre",
    "美樂": "Milre",
    "ailock": "AiLock",
    "3e": "3E",
    "小島": "3E",
    "waferlock": "Waferlock",
}

# 品牌 → 技能名後綴
_BRAND_SUFFIX: dict[str, str] = {
    "Chatlock": "chatlock",
    "Dormakaba": "dormakaba",
    "Philips": "philips",
    "Kaadas": "kaadas",
    "Milre": "milre",
    "AiLock": "ailock",
    "3E": "3e",
    "Waferlock": "waferlock",
}

# 需要品牌解析的基礎技能（有品牌版本的 ts-* 技能）
_BRAND_SPLIT_SKILLS: set[str] = {
    "ts-alarm", "ts-door-stuck", "ts-dual-auth",
    "ts-lock-tongue", "ts-power-drain", "ts-verification",
}


def _normalize_brand(brand: str | None) -> str | None:
    """將 silver doc 的 brand 欄位正規化為標準品牌名。"""
    if not brand or brand.lower() in ("general", "unknown", ""):
        return None
    return _BRAND_ALIASES.get(brand.lower(), brand)


def _resolve_brand_skill(
    base_skill: str,
    brand: str | None,
    registry: dict[str, SkillInfo] | None,
) -> str:
    """將基礎技能名 + 品牌解析為品牌版技能名。

    邏輯：
    1. 若基礎技能不在 _BRAND_SPLIT_SKILLS → 直接回傳（如 ts-auto-lock）
    2. 嘗試 {base}-{brand_suffix} → 若在 registry 中則採用
    3. 嘗試 {base}-other → 若在 registry 中則採用
    4. 回退到基礎技能名
    """
    if base_skill not in _BRAND_SPLIT_SKILLS:
        return base_skill

    if registry is None:
        return base_skill

    # 有品牌 → 嘗試品牌版
    if brand:
        suffix = _BRAND_SUFFIX.get(brand)
        if suffix:
            brand_skill = f"{base_skill}-{suffix}"
            if brand_skill in registry:
                return brand_skill

    # 無品牌或品牌版不存在 → 嘗試 -other
    other_skill = f"{base_skill}-other"
    if other_skill in registry:
        return other_skill

    return base_skill


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


def classify_tier1(
    doc: dict,
    chunk_index: int,
    registry: dict[str, SkillInfo] | None = None,
) -> Classification | None:
    """Tier 1 分類：metadata + 關鍵字，快速且免 LLM。

    品牌感知：分類完成後，依據 doc['brand'] 將 ts-* 基礎技能
    解析為品牌版技能名（如 ts-alarm → ts-alarm-dormakaba）。
    """
    content = doc.get("content", "")
    source_file = doc.get("_source_file", doc.get("source", "unknown"))
    category = doc.get("category", "")
    brand = _normalize_brand(doc.get("brand"))

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
            resolved = _resolve_brand_skill(result[0], brand, registry)
            return Classification(
                source_file=source_file,
                chunk_index=chunk_index,
                skill_name=resolved,
                confidence=result[1],
                method="keyword",
                reasoning=f"category=troubleshoot, keyword match, brand={brand or 'unknown'}",
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
        resolved = _resolve_brand_skill(result[0], brand, registry)
        return Classification(
            source_file=source_file,
            chunk_index=chunk_index,
            skill_name=resolved,
            confidence=result[1] - 0.1,  # 沒有 category 佐證，降低信心
            method="keyword",
            reasoning=f"no category, keyword match only, brand={brand or 'unknown'}",
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
        except (OSError, RuntimeError, ValueError, TimeoutError, ConnectionError) as e:
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
