"""Calibrate 階段 — 依客戶下輪反應分類，產 CalibrationSignal。

對齊新需求《AI客服 Harness設計策略》§5.4 + §8.3。

設計：
- CalibrationSignal 是「對 prior belief 的訊號」，不是新 belief
- Hypothesize 階段拿到 signal 後決定 belief 該怎麼修正：
  - DENY      → 排除上輪 top hypothesis 同方向的假設
  - CONFIRM   → 保留主方向，深化細節
  - ADD       → 同主題擴充
  - SHIFT     → 完全 reset hypothesis
  - IMPATIENT → 規則層直接強制 ESCALATE（policy 已實作可加 hook）
  - NEUTRAL   → 不影響，照常 Hypothesize

對外只需 ``calibrate(input, llm)`` 即可。

註：本檔 Hypothesize 化解程序與 hypothesize.py 鏡像（render → call → parse），
故意保留相同形狀方便比對。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Literal

from belief import BeliefState

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "calibrate.md"


CalibrationSignalType = Literal[
    "CONFIRM",
    "DENY",
    "ADD",
    "SHIFT",
    "IMPATIENT",
    "NEUTRAL",
]


@dataclass
class CalibrationSignal:
    """單輪 Calibrate 輸出。"""
    signal: CalibrationSignalType
    reason: str
    evidence_quote: str = ""


@dataclass
class CalibrateInput:
    """單輪 Calibrate 階段的輸入。"""
    user_message: str            # 本輪客戶訊息
    prior_belief: BeliefState    # 上輪 belief（top hypothesis 給 LLM 看）
    prior_ai_reply: str = ""     # 上輪 AI 給客戶的回覆


def _load_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_prior_situation(prior: BeliefState) -> str:
    if prior.top is None:
        return "（無）"
    top = prior.top
    lines = [
        f"- 描述：{top.description}",
        f"- 主要意圖：{top.primary_intent}",
        f"- 擁有狀態：{top.ownership_status}",
    ]
    if top.likely_misframe:
        lines.append(f"- 可能誤解：{top.likely_misframe}")
    return "\n".join(lines)


def render_prompt(inp: CalibrateInput) -> str:
    template = _load_template()
    sections = [
        template,
        "",
        "---",
        "",
        "[上輪客戶情境]",
        _format_prior_situation(inp.prior_belief),
        "",
        "[上輪 AI 回覆]",
        (inp.prior_ai_reply.strip() or "（無）"),
        "",
        "[本輪客戶訊息]",
        inp.user_message.strip(),
        "",
        "請輸出 JSON：",
    ]
    return "\n".join(sections)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


_VALID_SIGNALS = {"CONFIRM", "DENY", "ADD", "SHIFT", "IMPATIENT", "NEUTRAL"}


def parse_response(text: str) -> CalibrationSignal:
    """嚴格解析 LLM 回應為 CalibrationSignal。失敗 raise ValueError。"""
    raw = _extract_json(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"calibrate: invalid JSON: {e}; raw={raw[:200]!r}") from e

    if not isinstance(data, dict) or "signal" not in data:
        raise ValueError(f"calibrate: missing 'signal' key; got {list(data)[:5]}")

    sig = data["signal"]
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"calibrate: invalid signal {sig!r}; allowed={sorted(_VALID_SIGNALS)}")

    return CalibrationSignal(
        signal=sig,
        reason=str(data.get("reason", "")).strip(),
        evidence_quote=str(data.get("evidence_quote", "")).strip(),
    )


LLMCaller = Callable[[str], Awaitable[str]]


async def calibrate(
    inp: CalibrateInput,
    llm: LLMCaller,
    *,
    max_retries: int = 1,
) -> CalibrationSignal:
    """端到端跑 Calibrate：render → call LLM → parse → CalibrationSignal。

    Raises:
        ValueError: 重試完仍解析失敗
    """
    prompt = render_prompt(inp)
    last_err: Exception | None = None
    for _ in range(max_retries + 1):
        response = await llm(prompt)
        try:
            return parse_response(response)
        except ValueError as e:
            last_err = e
            continue
    assert last_err is not None
    raise last_err
