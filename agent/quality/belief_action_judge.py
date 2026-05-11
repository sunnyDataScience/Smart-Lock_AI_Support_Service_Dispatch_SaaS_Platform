"""Hypothesis-Action Consistency Judge — quality_check 過程指標。

對齊新需求《AI客服 Harness設計策略》§10.3。

問題：Belief-Augmented ReAct 把 [Belief Hint] 給 LLM 看；但 LLM 可能照
hint 走也可能不照。沒這層 judge 我們不知道 belief 真的影響行為，或只是
裝飾。

設計：純函式 + async judge call。輸入 belief.top + decision.action +
final AI 回覆，問 judge：「LLM 是否照 action 行為？」

四種 action 對應預期：
- COMMIT   → 答案是直接回應問題（不是反問、不是轉真人）
- PROBE    → 答案是針對 probe_dimension 的單一追問（不是全面回答、不是寒暄）
- EXPLORE  → 答案是開放式追問（不是斷言、不是直答）
- ESCALATE → 答案是轉真人（transfer_to_human 模板或同等文字）

inconsistent 不一定是 bad — 客戶可能在中途補充足夠資訊讓 LLM 直接答
是合理的「客戶 override」；但累計 inconsistent 率高 = belief 沒在引導
行為，要查 prompt。

== 使用方式 ==

quality_check.py 本身直接 invoke agent 不走 orchestrator，所以不會產生
belief_state。本模組設計成「離線跑 production 資料」用：

    # 範例：抓上週生產 belief_states + LINE 對話，跑 consistency 評分
    from belief_store import load_thread_timeline
    from quality.belief_action_judge import judge_consistency, summarize_consistency

    verdicts = []
    for belief in beliefs_from_db:
        ai_reply = fetch_ai_reply_from_audit_log(belief.thread_id, belief.turn_id)
        user_msg = fetch_user_msg(belief.thread_id, belief.turn_id)
        v = await judge_consistency(
            judge_model,
            top_description=belief.top.description,
            top_intent=belief.top.primary_intent,
            action_type=infer_action_from_audit(...),  # 或保存 ActionDecision 到 DB
            user_message=user_msg,
            ai_response=ai_reply,
        )
        verdicts.append(v)
    summary = summarize_consistency(verdicts)
    print(f"consistent_rate={summary['consistent_rate']:.1%}")

quality_check.py 整合（讓 synthetic test cases 也走 Turn Cycle）為後續工作。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any


JUDGE_PROMPT = """\
你是品質評審員。請判斷 AI 客服的回覆是否符合系統建議的動作。

## 系統內部建議（給 AI 的 Belief Hint）

- 最可能情境：{top_description}
- 主要意圖：{top_intent}
- 系統建議動作：{action_type}
- 動作說明：{action_hint}

## 客戶訊息

{user_message}

## AI 實際回覆

{ai_response}

## 評分標準

回答以下兩個維度：

1. **consistent**: AI 回覆是否符合系統建議的動作行為？
   - COMMIT 要求「直接答」，AI 確實直接答 → consistent
   - PROBE 要求「針對某 dimension 追問」，AI 確實追問 → consistent
   - EXPLORE 要求「開放式追問」，AI 確實開放式追問 → consistent
   - ESCALATE 要求「轉真人」，AI 確實叫 transfer_to_human 或給轉接訊息 → consistent
   - **客戶在 utterance 中已給足資訊讓 AI 可直答**（即使建議是 PROBE/EXPLORE），AI 直答 = consistent + 標 `override_reason: "user_supplied_info"`
   - AI 完全照 hint 走但客戶實際問題已脫離 hint → consistent + 標 `override_reason: "hint_stale"`

2. **inconsistent_severity**（僅當 consistent=false 時填）:
   - `low` — 行為差異但結果還可接受（例：建議 PROBE 卻直答，但答案恰好對）
   - `mid` — 明顯偏離且結果不佳（例：建議 ESCALATE 卻硬答）
   - `high` — 嚴重偏離（例：建議 COMMIT 卻轉真人浪費）

請只回 JSON，不要 markdown code block：
{{"consistent": true/false, "inconsistent_severity": "low/mid/high/null", "override_reason": "user_supplied_info/hint_stale/null", "reason": "一句話說明"}}
"""


_ACTION_HINT_TEXT = {
    "COMMIT":   "信心夠，直接答客戶問題",
    "PROBE":    "信心並列，先針對某 dimension 追問一次再答",
    "EXPLORE":  "情境模糊，用一句開放式追問引導客戶補充",
    "ESCALATE": "此情境應轉真人，AI 不該硬答",
}


@dataclass
class ConsistencyVerdict:
    """單筆 hypothesis-action consistency 評分結果。"""
    consistent: bool
    inconsistent_severity: str | None  # "low" / "mid" / "high" / None
    override_reason: str | None        # "user_supplied_info" / "hint_stale" / None
    reason: str

    @classmethod
    def from_dict(cls, data: dict) -> "ConsistencyVerdict":
        sev = data.get("inconsistent_severity")
        if sev in ("null", "None", ""):
            sev = None
        ovr = data.get("override_reason")
        if ovr in ("null", "None", ""):
            ovr = None
        return cls(
            consistent=bool(data.get("consistent", False)),
            inconsistent_severity=sev,
            override_reason=ovr,
            reason=str(data.get("reason", "")).strip(),
        )


async def judge_consistency(
    judge_model: Any,
    *,
    top_description: str,
    top_intent: str,
    action_type: str,
    user_message: str,
    ai_response: str,
) -> ConsistencyVerdict:
    """跑一次 hypothesis-action consistency judge。

    Args:
        judge_model: LangChain ChatModel (ChatLiteLLM / ChatVertexAI 等)
        top_description: belief.top.description
        top_intent: belief.top.primary_intent
        action_type: "COMMIT"/"PROBE"/"EXPLORE"/"ESCALATE"
        user_message: 客戶 utterance
        ai_response: AI 最終回覆

    Raises:
        ValueError: judge 回應無法解析為 JSON / 缺欄位
    """
    prompt = JUDGE_PROMPT.format(
        top_description=top_description,
        top_intent=top_intent,
        action_type=action_type,
        action_hint=_ACTION_HINT_TEXT.get(action_type, "(unknown action)"),
        user_message=user_message,
        ai_response=ai_response,
    )

    try:
        from harness.llm_metrics import log_simple as _log_simple
    except ImportError:
        _log_simple = None
    model_name = getattr(judge_model, "model", "unknown") or "unknown"
    t0 = time.monotonic()
    resp = await judge_model.ainvoke(prompt)
    if _log_simple:
        _log_simple(
            user_id="quality:belief_action_consistency",
            call_site="quality_belief_action_judge",
            model=str(model_name),
            response=resp,
            latency_ms=int((time.monotonic() - t0) * 1000),
            user_question=prompt,
            metadata={"action": action_type},
        )

    content = resp.content
    if isinstance(content, list):
        content = "".join(
            b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"belief_action_judge: invalid JSON: {e}; raw={content[:200]!r}") from e

    if "consistent" not in data:
        raise ValueError(f"belief_action_judge: missing 'consistent' key; got {list(data)[:5]}")

    return ConsistencyVerdict.from_dict(data)


def summarize_consistency(verdicts: list[ConsistencyVerdict]) -> dict:
    """彙整一批 verdict 算通過率 + 嚴重度分布，給 quality_check 報表用。"""
    if not verdicts:
        return {
            "total": 0,
            "consistent": 0,
            "consistent_rate": 0.0,
            "severity_breakdown": {"low": 0, "mid": 0, "high": 0},
            "override_breakdown": {"user_supplied_info": 0, "hint_stale": 0},
        }

    total = len(verdicts)
    consistent = sum(1 for v in verdicts if v.consistent)
    severity = {"low": 0, "mid": 0, "high": 0}
    override = {"user_supplied_info": 0, "hint_stale": 0}
    for v in verdicts:
        if v.inconsistent_severity in severity:
            severity[v.inconsistent_severity] += 1
        if v.override_reason in override:
            override[v.override_reason] += 1

    return {
        "total": total,
        "consistent": consistent,
        "consistent_rate": consistent / total,
        "severity_breakdown": severity,
        "override_breakdown": override,
    }
