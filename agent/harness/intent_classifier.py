"""F-014/F-015 dual-trigger LINE 自助路徑 — intent classifier。

ADR-009 §8 D1 dual-trigger 的 (a) path：消費者在 LINE 訊息中表達「退款」/「保固」
意圖時，agent 偵測後自動觸發 AdminAPIClient.create_refund_request /
create_warranty_claim。

V1.0 MVP: keyword-based 快速比對（無 LLM cost、< 1ms）
V2.0 升級: Haiku first-pass + confidence threshold（ADR-009 §8 D5）
        當 keyword 命中但 confidence 低時，讓 Haiku 二次確認；混淆 case
        （如「保固期內想退款」）才升 main model。

實際呼叫 admin api 的整合點：debounce.process_and_reply 或 agent post-processing
hook（呼叫 AdminAPIClient.create_*；本檔只負責偵測）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("agent.harness.intent_classifier")


# ── Intent keywords（正規化為小寫，比對前 lower） ──
_REFUND_KEYWORDS = {
    "退款", "退費", "退錢", "拿回錢", "我要退",
    "申請退款", "退服務費", "想要退",
}

_WARRANTY_KEYWORDS = {
    "保固", "保修", "保用", "壞了沒多久", "才買", "保固期內",
    "申請保固", "保固理賠", "在保固",
}


def detect_intent(text: str) -> str | None:
    """偵測使用者訊息中的退款 / 保固意圖。

    Returns:
        'refund' / 'warranty' / None

    V1.0 keyword-based，confidence 暫不回傳；V2.0 升級到 LLM-based 才補
    confidence + threshold gating（ADR-009 §8 D5 規範）。
    """
    if not text:
        return None
    normalized = text.strip().lower()

    if any(kw in normalized for kw in _REFUND_KEYWORDS):
        # 同時提到「保固」+「退款」→ 視為 refund 優先（金錢面 priority 高）
        return "refund"
    if any(kw in normalized for kw in _WARRANTY_KEYWORDS):
        return "warranty"
    return None


def get_intent_confidence(text: str, intent: str) -> float:
    """V2.0 placeholder — keyword-based 暫時都回 1.0。

    未來升級 Haiku LLM 後，回 0~1 confidence；< 0.7 升 main model 二判。
    """
    if not text or not intent:
        return 0.0
    return 1.0
