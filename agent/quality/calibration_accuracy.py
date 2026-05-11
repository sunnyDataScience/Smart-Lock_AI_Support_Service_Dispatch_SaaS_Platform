"""Calibration Accuracy metric — Calibrate step 是否真的修正了 belief。

對齊新需求《AI客服 Harness設計策略》§10.2 過程指標：
- 否認（DENY）後是否淘汰錯誤假設
- 不耐煩（IMPATIENT）後是否切 ESCALATE

設計：純規則分析，不打 LLM。輸入是 timeline（多個 turn 的 (prior_belief,
signal, next_belief, next_action) 序列），輸出每個 signal 類別的 accuracy。

不是黑白判定 — DENY 後 belief 改方向是「對的」，但若 belief 沒變但
action 變了（從 PROBE 變 COMMIT）有時也是合理（客戶其實要的就在第二
hypothesis）。本 metric 用「方向是否變動」為粗篩，配合 ConsistencyVerdict
（quality/belief_action_judge.py）才能做完整判斷。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# 讓本模組從 quality/ 子目錄 import 上層 agent/ 模組
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from belief import BeliefState


@dataclass
class TurnTransition:
    """單筆相鄰兩輪的 belief + signal + action 觀察點。"""
    prior_belief: BeliefState
    signal: str            # CONFIRM/DENY/ADD/SHIFT/IMPATIENT/NEUTRAL
    next_belief: BeliefState
    next_action: str       # COMMIT/PROBE/EXPLORE/ESCALATE


# 不同 signal 期待的 belief 行為
# 「expected_change」: True 代表 belief 應變方向；False 代表應留同方向
_EXPECTED_CHANGE = {
    "CONFIRM":   False,   # 同方向，細節深化
    "DENY":      True,    # 反方向，淘汰錯假設
    "ADD":       False,   # 同方向，加細節
    "SHIFT":     True,    # 換話題，新方向
    "IMPATIENT": True,    # 切 ESCALATE
    "NEUTRAL":   None,    # 不評（無 ground truth）
}


def _intent_changed(prior: BeliefState, next_: BeliefState) -> bool:
    """top hypothesis 的 primary_intent 是否變了。"""
    if prior.top is None or next_.top is None:
        return False
    return prior.top.primary_intent != next_.top.primary_intent


def _description_changed(prior: BeliefState, next_: BeliefState) -> bool:
    """粗略判 top description 是否實質變動（字串比較）。"""
    if prior.top is None or next_.top is None:
        return False
    return prior.top.description.strip() != next_.top.description.strip()


def _belief_changed(prior: BeliefState, next_: BeliefState) -> bool:
    """belief 在「方向」上是否有變（intent 或 description 任一變即算）。"""
    return _intent_changed(prior, next_) or _description_changed(prior, next_)


def evaluate_transition(t: TurnTransition) -> dict:
    """評估單筆 transition 的校準準確度。

    Returns:
        {
            "signal": "DENY",
            "expected_change": True,
            "belief_changed": True,
            "action_escalated": False,
            "accurate": True,
            "notes": "...",
        }
    """
    expected = _EXPECTED_CHANGE.get(t.signal)
    belief_changed = _belief_changed(t.prior_belief, t.next_belief)
    action_escalated = t.next_action == "ESCALATE"

    # IMPATIENT 特例：accuracy = action 真的切到 ESCALATE
    if t.signal == "IMPATIENT":
        accurate = action_escalated
        notes = (
            "IMPATIENT → 應切 ESCALATE"
            if accurate
            else f"IMPATIENT 但 action={t.next_action}（規則層失效？）"
        )
    elif expected is None:
        # NEUTRAL：不評
        accurate = True
        notes = "NEUTRAL — 無 ground truth"
    else:
        accurate = belief_changed == expected
        notes = (
            f"signal={t.signal}：期望 belief 改向={expected}，實際={belief_changed}"
            if not accurate
            else f"signal={t.signal}：期望符合"
        )

    return {
        "signal": t.signal,
        "expected_change": expected,
        "belief_changed": belief_changed,
        "action_escalated": action_escalated,
        "accurate": accurate,
        "notes": notes,
    }


@dataclass
class CalibrationAccuracyReport:
    total: int
    accurate: int
    per_signal: dict[str, dict]  # signal → {"total": n, "accurate": n, "rate": f}

    @property
    def overall_rate(self) -> float:
        return self.accurate / self.total if self.total else 0.0


def evaluate_timeline(transitions: list[TurnTransition]) -> CalibrationAccuracyReport:
    """彙整一條對話 timeline 的 calibration accuracy。

    NEUTRAL 仍計入 total 但「accurate」永遠為 True（不影響 baseline）。
    """
    if not transitions:
        return CalibrationAccuracyReport(total=0, accurate=0, per_signal={})

    per_signal: dict[str, dict] = {}
    overall_accurate = 0
    for t in transitions:
        result = evaluate_transition(t)
        sig = result["signal"]
        bucket = per_signal.setdefault(sig, {"total": 0, "accurate": 0, "rate": 0.0})
        bucket["total"] += 1
        if result["accurate"]:
            bucket["accurate"] += 1
            overall_accurate += 1

    for sig, bucket in per_signal.items():
        bucket["rate"] = bucket["accurate"] / bucket["total"]

    return CalibrationAccuracyReport(
        total=len(transitions),
        accurate=overall_accurate,
        per_signal=per_signal,
    )
