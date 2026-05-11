"""把 (BeliefState, ActionDecision) 渲染成 system prompt prefix。

Belief-Augmented ReAct 策略：不取代 ReAct，把 Hypothesize + Decide 的結果
作為 hint 注入 prompt 引導行為。

對齊 system.md「若收到 [Belief Hint] 區塊，依其指示動作」的契約。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from belief import BeliefState
from policy import ActionDecision


# probe_dimension → 自然語言提示（給 LLM 看的，告訴它「該追問哪一面」）
_PROBE_DIM_HINTS = {
    "intent": "客戶意圖（是要排障、查規格、報價，還是別的）",
    "ownership": "客戶是否擁有產品（已買 / 還在挑選 / 完全沒提）",
    "symptom": "故障細節（什麼時候發生、什麼徵狀、什麼前置動作）",
    "product": "產品本身（品牌、型號、購買通路）",
}


def render_belief_hint(belief: BeliefState, decision: ActionDecision) -> str:
    """渲染 [Belief Hint] 區塊。

    Returns:
        多行字串，結尾兩個 \\n（讓 caller 拼接乾淨）。
        若 belief 沒任何 hypothesis 就回空字串。
    """
    if belief.top is None:
        return ""

    top = belief.top
    lines = [
        "[Belief Hint]",
        f"（系統已先分析客戶情境，給你以下引導；若與你獨立判斷衝突，以客戶實際訊息為準）",
        f"- 最可能情境：{top.description}（信心 {top.confidence:.2f}）",
        f"- 主要意圖：{top.primary_intent}",
        f"- 擁有狀態：{top.ownership_status}",
    ]

    if len(belief.hypotheses) >= 2:
        runner = belief.hypotheses[1]
        lines.append(
            f"- 第二可能：{runner.description}（信心 {runner.confidence:.2f}）"
        )

    lines.append(f"- 建議動作：{decision.action}")

    if decision.action == "COMMIT":
        lines.append("→ 信心夠，**直接答客戶問題**，不要先反問")
    elif decision.action == "PROBE":
        dim = _PROBE_DIM_HINTS.get(decision.probe_dimension or "", "關鍵未確定處")
        lines.append(f"→ 假設並列未拉開，**先針對「{dim}」追問**再答")
    elif decision.action == "EXPLORE":
        lines.append("→ 情境模糊，**用一句開放式追問**讓客戶補充，不要硬猜")
    elif decision.action == "ESCALATE":
        # ESCALATE 旁路 ReAct，但保留 hint 文字方便日後改走 ReAct
        lines.append("→ 此情境應轉真人；不要硬答")

    return "\n".join(lines) + "\n\n"
