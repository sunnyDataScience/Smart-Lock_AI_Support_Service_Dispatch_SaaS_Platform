"""Hypothesize 階段 — 從 utterance + 歷史 + 知識產出 BeliefState。

對齊新需求《AI客服 Harness設計策略》§8.1 Three-layer Meta-Skill 第一層。

本模組提供：
- HypothesizeInput dataclass — 結構化輸入
- render_prompt(...) — 把 Hypothesize template 填入實際內容
- parse_response(text) — 嚴格 JSON 解析 + schema validation
- hypothesize(input, llm) — 端到端：render → call LLM → parse → BeliefState
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from belief import BeliefState, Hypothesis

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "hypothesize.md"


@dataclass
class HypothesizeInput:
    """單輪 Hypothesize 階段的所有輸入。"""
    user_message: str
    history: list[dict] = field(default_factory=list)  # [{role, content}, ...] 最近 3 輪
    prior_belief: BeliefState | None = None
    catalog_block: str = ""    # profiles.context.format_catalog_section() 的輸出
    user_facts_block: str = "" # [用戶資料] 區塊


def _format_history(history: list[dict]) -> str:
    if not history:
        return "（無）"
    lines = []
    for msg in history[-6:]:  # 對話歷史保留最近 3 輪 = 最多 6 則訊息
        role = "客戶" if msg.get("role") == "user" else "AI"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "（無）"


def _format_prior_belief(belief: BeliefState | None) -> str:
    if belief is None or not belief.hypotheses:
        return "null"
    return belief.to_json()


def _load_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def render_prompt(inp: HypothesizeInput) -> str:
    """把 inputs 接在 hypothesize.md template 後面，給 LLM。"""
    template = _load_template()
    sections = [
        template,
        "",
        "---",
        "",
        "[本輪客戶訊息]",
        inp.user_message.strip(),
        "",
        "[對話歷史]",
        _format_history(inp.history),
        "",
        "[既有 belief]",
        _format_prior_belief(inp.prior_belief),
        "",
    ]
    if inp.catalog_block.strip():
        sections.extend([inp.catalog_block.strip(), ""])
    if inp.user_facts_block.strip():
        sections.extend([inp.user_facts_block.strip(), ""])
    sections.append("請輸出 JSON：")
    return "\n".join(sections)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """LLM 偶爾會包 ```json fence，剝掉。"""
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1)
    # 沒 fence 就找第一個 { 到最後一個 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_response(text: str, turn_id: int = 0) -> BeliefState:
    """嚴格解析 LLM 回應為 BeliefState。失敗 raise ValueError。"""
    raw = _extract_json(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"hypothesize: invalid JSON: {e}; raw={raw[:200]!r}") from e

    if not isinstance(data, dict) or "hypotheses" not in data:
        raise ValueError(f"hypothesize: missing 'hypotheses' key; got {list(data)[:5]}")

    hyps_raw = data["hypotheses"]
    if not isinstance(hyps_raw, list) or not hyps_raw:
        raise ValueError("hypothesize: 'hypotheses' must be non-empty list")
    if len(hyps_raw) > 3:
        hyps_raw = hyps_raw[:3]

    hyps: list[Hypothesis] = []
    for h in hyps_raw:
        try:
            misframe = h.get("likely_misframe")
            if misframe is not None:
                misframe = str(misframe).strip() or None
            hyps.append(Hypothesis(
                description=str(h["description"]).strip(),
                confidence=float(h["confidence"]),
                primary_intent=h["primary_intent"],
                ownership_status=h["ownership_status"],
                likely_misframe=misframe,
            ))
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"hypothesize: malformed hypothesis {h!r}: {e}") from e

    hyps.sort(key=lambda h: h.confidence, reverse=True)
    return BeliefState(hypotheses=hyps, turn_id=turn_id)


# Callable type alias — 抽象 LLM 介面，方便測試替換
LLMCaller = Callable[[str], Awaitable[str]]


async def hypothesize(
    inp: HypothesizeInput,
    llm: LLMCaller,
    *,
    turn_id: int = 0,
    max_retries: int = 1,
) -> BeliefState:
    """端到端跑 Hypothesize：render → call LLM → parse → BeliefState。

    Args:
        inp: 本輪所有輸入
        llm: 接受 prompt 字串、回傳完整回應字串的 async callable
        turn_id: 本輪序號（寫進 BeliefState）
        max_retries: 若 LLM JSON 不合法，最多重試幾次

    Raises:
        ValueError: 重試完仍解析失敗
    """
    prompt = render_prompt(inp)
    last_err: Exception | None = None
    for _ in range(max_retries + 1):
        response = await llm(prompt)
        try:
            return parse_response(response, turn_id=turn_id)
        except ValueError as e:
            last_err = e
            continue
    assert last_err is not None
    raise last_err
