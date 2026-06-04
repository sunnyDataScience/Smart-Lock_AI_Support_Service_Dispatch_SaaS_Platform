"""LLM 記憶抽取器 — 取代 default_extractor(原本整句存)。

把一輪對話交給 LLM,只抽出「值得長期記住的客人事實」(鎖品牌型號、聯絡方式、
偏好、未解問題),並過濾閒聊噪音(美食、股票等)。對應 Hermes 的 memory-only 審查精神。

輸出 (kind, content) list;kind 限 store 的 VALID_KINDS。任何錯誤都回空 list
(SAVE 端已包 try/except,記憶寫入絕不可讓 turn 失敗)。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from .store import VALID_KINDS

_SYSTEM = (
    "你是鎖匠客服的記憶抽取器。讀「客人訊息」與「客服回覆」,只抽出『值得長期記住、"
    "未來服務這位客人會用到』的事實,輸出 JSON 陣列,每項 {\"kind\":..., \"content\":...}。\n"
    "kind 僅能是:profile(身分/聯絡:電話、地址、姓名)、preference(偏好)、"
    "fact(客觀事實:鎖的品牌型號、安裝日期)、issue(待解問題)、dispatch(已派工/已轉真人)。\n"
    "content 寫成精煉的第三人稱事實,例如「客人的鎖是 Dormakaba AS701」「客人電話 0912-345-678」。\n"
    "規則:① 閒聊或與本店服務無關(美食、天氣、股票)→ 不要抽,該項略過。\n"
    "② 一次性的操作問題(怎麼改密碼)本身不是事實,但其中透露的型號要抽成 fact。\n"
    "③ 沒有任何值得記的 → 回 []。④ 只輸出 JSON 陣列,不要多餘文字。"
)


def _parse(text: str) -> list[tuple[str, str]]:
    """從模型輸出解析出 (kind, content);容忍 ```json 圍欄與雜訊。"""
    if not text:
        return []
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        items = json.loads(s[start : end + 1])
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[tuple[str, str]] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        kind = str(it.get("kind", "")).strip()
        content = str(it.get("content", "")).strip()
        if kind in VALID_KINDS and content:
            out.append((kind, content))
    return out


class LLMExtractor:
    """以 LLM 抽乾淨事實的抽取器(可呼叫物件,async)。"""

    def __init__(self, provider: Any, model: str | None = None, max_facts: int = 6):
        self._provider = provider
        self._model = model
        self._max_facts = max_facts

    async def __call__(self, user_msg: str, assistant_msg: str) -> list[tuple[str, str]]:
        if not (user_msg or "").strip():
            return []
        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"客人訊息:\n{user_msg}\n\n客服回覆:\n{assistant_msg or '(無)'}",
            },
        ]
        try:
            resp = await self._provider.chat(
                messages=messages, model=self._model, max_tokens=512, temperature=0.0
            )
        except Exception:
            logger.exception("LLMExtractor: chat 失敗,回空")
            return []
        if getattr(resp, "finish_reason", None) == "error":
            logger.warning("LLMExtractor: provider 回 error,回空")
            return []
        return _parse(getattr(resp, "content", "") or "")[: self._max_facts]
