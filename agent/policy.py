"""Action Decision Policy — 規則層 sanity check。

對齊新需求《AI客服 Harness設計策略》§7 Action Policy。

LLM 在 Hypothesize 階段已提出 belief。本層用 confidence threshold + intent
+ ownership_status 決定下一步動作，給 Execute 階段執行。

設計原則（新需求 §7.1）：
- LLM 隱性決策容易出包（金錢字眼一律轉真人 → 文不對題、追問沒給答案、
  過早派工）。改用「LLM 提議 + 規則 sanity check」混合策略
- 規則優先級：意圖類型 > confidence > ownership_status
- 規則層拒絕條件就標 ESCALATE，不靠 LLM 自己選

四種動作：
- COMMIT    — 直接答客戶問題（高 confidence）
- PROBE     — 問特定追問題（中 confidence；情境不清楚）
- EXPLORE   — 開放式追問（低 confidence；連方向都不知道）
- ESCALATE  — 轉真人（價格、合約、爭議；非 AI 該答的）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from belief import BeliefState, Hypothesis


ActionType = Literal["COMMIT", "PROBE", "EXPLORE", "ESCALATE"]


# Confidence thresholds — 新需求 §7.2 預設值
HIGH_CONFIDENCE = 0.70   # >= HIGH → COMMIT
LOW_CONFIDENCE = 0.30    # < LOW   → EXPLORE
# (LOW, HIGH] 之間 → PROBE

# Top vs runner-up gap — top 沒拉開就算「並列」，要 PROBE 區分
GAP_TO_COMMIT = 0.30


# 規則層強制 ESCALATE 的 intent
_ESCALATE_INTENTS = {"quote_request", "dispatch_request"}


@dataclass
class ActionDecision:
    """規則層判定結果。"""
    action: ActionType
    reason: str
    target_hypothesis: Hypothesis | None
    # PROBE / EXPLORE 時：要問哪個 dimension（'intent' / 'ownership' / 'product' / 'symptom'）
    probe_dimension: str | None = None


def _runner_up_confidence(belief: BeliefState) -> float:
    if len(belief.hypotheses) >= 2:
        return belief.hypotheses[1].confidence
    return 0.0


def _select_probe_dimension(belief: BeliefState) -> str:
    """選 information-gain 最高的 dimension 去 probe。

    啟發式（不做完整 IG 計算，先用簡易判斷）：
    - 若 top 跟 runner-up 的 ownership_status 不同 → 問 ownership
    - 若 top 跟 runner-up 的 primary_intent 不同 → 問 intent
    - 否則 → 問 product / symptom 細節
    """
    if len(belief.hypotheses) < 2:
        return "intent"
    top, runner = belief.hypotheses[0], belief.hypotheses[1]
    if top.ownership_status != runner.ownership_status:
        return "ownership"
    if top.primary_intent != runner.primary_intent:
        return "intent"
    return "symptom"


def decide(belief: BeliefState) -> ActionDecision:
    """根據 BeliefState 規則層判定下一步動作。

    Args:
        belief: 本輪 Hypothesize 階段輸出

    Returns:
        ActionDecision — Execute 階段依此跑回應流程
    """
    top = belief.top
    if top is None:
        return ActionDecision(
            action="EXPLORE",
            reason="no hypothesis produced — ask open-ended",
            target_hypothesis=None,
            probe_dimension="intent",
        )

    # 規則 1：強制 ESCALATE 意圖（不看 confidence）
    if top.primary_intent in _ESCALATE_INTENTS:
        return ActionDecision(
            action="ESCALATE",
            reason=f"intent={top.primary_intent} → 規則層強制轉真人",
            target_hypothesis=top,
        )

    # 規則 2：信心 >= HIGH 且 top 拉開 runner-up → COMMIT
    gap = top.confidence - _runner_up_confidence(belief)
    if top.confidence >= HIGH_CONFIDENCE and gap >= GAP_TO_COMMIT:
        return ActionDecision(
            action="COMMIT",
            reason=f"top conf={top.confidence:.2f} >= {HIGH_CONFIDENCE} 且 gap={gap:.2f} >= {GAP_TO_COMMIT}",
            target_hypothesis=top,
        )

    # 規則 3：信心 < LOW → EXPLORE（連方向都不確定）
    if top.confidence < LOW_CONFIDENCE:
        return ActionDecision(
            action="EXPLORE",
            reason=f"top conf={top.confidence:.2f} < {LOW_CONFIDENCE} — 開放式追問",
            target_hypothesis=top,
            probe_dimension=_select_probe_dimension(belief),
        )

    # 規則 4：(LOW, HIGH) 或 gap 不夠 → PROBE
    return ActionDecision(
        action="PROBE",
        reason=(
            f"top conf={top.confidence:.2f}, gap={gap:.2f} — "
            f"信心中等或並列假設未拉開，需特定追問"
        ),
        target_hypothesis=top,
        probe_dimension=_select_probe_dimension(belief),
    )
