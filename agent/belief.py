"""BeliefState — Hypothesis-Driven harness 的核心物件。

對齊新需求《AI客服 Harness設計策略》§6.1 Schema 設計第一版：最小可跑欄位。
不放 evidence / contradicting_evidence / likely_misframe（schema v2/v3 才加）。

每輪 Turn Cycle 維護一個 BeliefState：
    Hypothesize → 產出 / 更新 hypothesis list
    Decide     → 依 confidence + ownership_status 決定 action
    Execute    → 跑 action（答覆 / probe / load doc / escalate）
    Calibrate  → 依客戶下一輪反應更新 belief

BeliefState 是純資料，沒有方法。Hypothesize / Decide / Calibrate 都是
「拿 BeliefState 進、產 BeliefState 出」的純函式或 prompt module。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal
import json
import uuid


PrimaryIntent = Literal[
    "troubleshoot",      # 故障排除
    "spec_question",     # 規格諮詢
    "service_yesno",     # 是非題（有沒有 X 服務）
    "quote_request",     # 報價
    "dispatch_request",  # 派工 / 預約安裝
    "small_talk",        # 寒暄
    "unclear",           # 還沒看出意圖
]

OwnershipStatus = Literal[
    "owned",         # 已知品牌+型號
    "brand_only",    # 只有品牌
    "considering",   # 考慮購買，尚未持有
    "unknown",       # 完全未知
]


@dataclass
class Hypothesis:
    """單一假設。description 自然語言，confidence 為 0-1 連續值。

    likely_misframe 為 v2 schema 新增（業主強調的能力差距）：客戶用的字眼
    可能跟我們的領域詞不一致（「卡卡的」可能是門五金、鎖芯、app 三種誤判），
    LLM 在 Hypothesize 階段標出**這個 hypothesis 最可能誤解客戶哪件事**。
    None 代表 LLM 沒識別出 misframe（如「AS850 加卡步驟」這類明確訊息）。
    """
    description: str
    confidence: float
    primary_intent: PrimaryIntent
    ownership_status: OwnershipStatus
    likely_misframe: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0,1], got {self.confidence}"
            )


@dataclass
class BeliefState:
    """單輪 Turn Cycle 結束後對「客戶目前情境」的整體 belief。

    - hypotheses: 1-3 個 ranked，confidence 由高到低
    - top: 便利屬性，等於 hypotheses[0]（若空清單則 None）
    - turn_id: 本輪在對話中的 0-indexed 序號
    - belief_id: 跨輪追溯 ID（持久化用）
    """
    hypotheses: list[Hypothesis] = field(default_factory=list)
    turn_id: int = 0
    belief_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def top(self) -> Hypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None

    @property
    def top_confidence(self) -> float:
        return self.top.confidence if self.top else 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "BeliefState":
        hyps = [Hypothesis(**h) for h in data.get("hypotheses", [])]
        return cls(
            hypotheses=hyps,
            turn_id=data.get("turn_id", 0),
            belief_id=data.get("belief_id", uuid.uuid4().hex),
        )


def empty_belief(turn_id: int = 0) -> BeliefState:
    """工廠函式：第 0 輪起手沒有任何 hypothesis 時用。"""
    return BeliefState(turn_id=turn_id)
