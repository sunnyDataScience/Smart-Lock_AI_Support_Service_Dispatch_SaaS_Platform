"""生成後回覆 guard（ADR-025 server-side enforce／CR-0152）。

憲章要求「不依賴 prompt」：價格 utterance（金額數字未轉真人就出口）與
未溯源型號（客戶沒提過的具體型號代碼＝幻覺訊號）屬確定性 regex 判定，
在 loop 出口攔截——修正重生 1 次，仍違規改走轉真人話術＋記 escalation
（業主裁決 2026-07-10）。

純函式（無 I/O、無相依），檢測邏輯與 CI 層 scripts/redline_gate.py、
scripts/grounding_guard.py 同源；接線於 loop._state_run 尾端。
"""

from __future__ import annotations

import re

# 報價數字（同 redline_gate）：NT$/$/＄+數字，或 數字+元/塊/台幣
_PRICE_RE = re.compile(r"(NT\$|＄|\$)\s*\d|[\d,]+\s*(元|塊|台幣|新台幣)")

# 具體型號代碼（同 grounding_guard）：≥2 大寫字母＋可選分隔＋≥3 位數字
_MODEL_CODE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*[- ]?\d{3,}[A-Z0-9]*)\b")

# 聲稱轉接/專員將聯繫的「確定式宣告」語彙（CR-0166 R0，K8 warranty_free say-do gap）：
# 嘴上說已轉接/會有專員聯繫，本 turn 卻沒呼叫 transfer_to_human = 案子蒸發。
# 刻意只收「確定式」宣告，不含「可以為您轉接嗎」這類提議句（避免強迫未確認的轉接）。
_CLAIMED_TRANSFER_MARKERS = (
    "已為您轉接", "已幫您轉接", "已為您將案件轉接", "已將您的案件轉接", "已轉接",
    "我將為您轉接", "我將協助您轉接", "幫您轉接給", "為您轉接給", "已通報專員",
    "已為您安排轉接", "已安排專員", "專員會與您聯繫", "專員將會與您聯繫",
    "會有專員與您聯繫", "專員稍後會", "專員將盡快與您聯繫", "已為您記錄並轉",
)

# 違規時的修正指令（regen 1 次用）
CORRECTIVE_INSTRUCTION = (
    "（系統修正指示，客戶看不到）你上一則草稿違反話術邊界："
    "回覆不得包含任何價格金額數字（報價一律轉真人），"
    "不得講出客戶未提過的具體型號代碼（不確定型號就開放式詢問）；"
    "若你聲稱「已轉接／會有專員聯繫」，就必須在本輪實際呼叫 transfer_to_human 工具"
    "（只說不呼叫＝案子蒸發）。"
    "請重寫回覆：移除違規內容，必要時使用 transfer_to_human 工具轉真人。"
)

# regen 後仍違規的固定轉真人話術（server-generated，不含任何數字/型號）
TRANSFER_FALLBACK = (
    "這部分涉及報價與型號確認，為避免資訊有誤，我先為您轉接真人專員協助，"
    "請稍候一下 🙏"
)


def _codes(text: str) -> set[str]:
    return {
        m.group(1).upper().replace(" ", "").replace("-", "")
        for m in _MODEL_CODE.finditer(text or "")
    }


def price_violation(reply: str, *, escalated: bool) -> bool:
    """回覆含價格數字且本 turn 未轉真人 → 違規（已轉真人時允許話術帶語境）。"""
    return bool(_PRICE_RE.search(reply or "")) and not escalated


def unsourced_model_codes(reply: str, customer_text: str) -> list[str]:
    """回覆出現、但客戶對話（含歷史）從未提到的具體型號代碼。"""
    return sorted(_codes(reply) - _codes(customer_text))


def claimed_transfer_violation(reply: str, *, escalated: bool) -> bool:
    """確定式宣告已轉接/專員將聯繫，但本 turn 未實際呼叫 transfer_to_human → 違規。

    CR-0166 R0（K8 warranty_free 裁定）：say-do gap——SOP 單一進線鐵律的
    runtime 兜底（SKILL.md 只約束 prompt 層，憲章要求不依賴 prompt）。
    """
    return not escalated and any(m in (reply or "") for m in _CLAIMED_TRANSFER_MARKERS)


def guard_violations(reply: str, customer_text: str, *, escalated: bool) -> list[str]:
    """回傳違規原因清單（空＝通過）。"""
    out: list[str] = []
    if price_violation(reply, escalated=escalated):
        out.append("price_utterance")
    codes = unsourced_model_codes(reply, customer_text)
    if codes:
        out.append("unsourced_model:" + ",".join(codes[:5]))
    if claimed_transfer_violation(reply, escalated=escalated):
        out.append("claimed_transfer_without_tool")
    return out
