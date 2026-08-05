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

# 報價數字（同 redline_gate）：NT$/$/＄+數字，或 數字+元/塊/台幣。
# 2026-07-27：原本只認阿拉伯數字 → 中文數字報價（「一千五百元」「兩千塊」「壹仟元」）
# 完全不攔，而中文客服語境用中文數字報價相當自然，等於紅線有破口。補中文數字分支。
_CJK_NUM = "零一二三四五六七八九十百千萬兩壹貳參叄肆伍陸柒捌玖拾佰仟萬"
_PRICE_RE = re.compile(
    r"(NT\$|＄|\$)\s*\d"
    r"|[\d,]+\s*(元|塊|台幣|新台幣)"
    rf"|[{_CJK_NUM}]+\s*(元|塊|台幣|新台幣)"
)

# 具體型號代碼（同 grounding_guard）：≥2 大寫字母＋可選分隔＋≥3 位數字。
# 只認得 Dormakaba 那種 AS701/ML550 形狀。
_MODEL_CODE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*[- ]?\d{3,}[A-Z0-9]*)\b")

# 2026-07-27 補漏：真實型號命名遠比上面 regex 的假設多樣 —— Chatlock `A90`（1 字母+2 數字）、
# Milre `6500F`（數字開頭）、Philips `7300`（純數字）、3E `TX` 等一律漏判，等於 grounding
# guard 只守住一個品牌。放寬 regex 會誤傷（純數字 7300 會撞到價格字串），故改用「知識庫實際
# 型號清單」做精確比對——deterministic、零誤判。
#
# ⚠️ 維護：本清單須與 `lockcore/skills/locksmith-product-knowledge/references/{Brand}/*.md`
# 同步；新增產品後請一併更新。`agent/tests/test_reply_guard_model_list.py` 會比對兩者，
# 漂移即測試失敗（不必人工記得）。
_KNOWN_MODELS: frozenset[str] = frozenset({
    # Dormakaba
    "AS701", "AS850", "AS901", "DP850", "FA9000", "FSL800", "GL220",
    "ML550", "ML660", "ML770", "MP750", "RL320", "RL360", "RL360V", "RL599", "Rose",
    # Chatlock
    "A90", "AI-88", "AI-99",
    # Milre
    "6500F", "6500S", "7150+",
    # Philips
    "702E", "7300", "9200", "9300", "Alpha",
    # 3E
    "TX", "F(T7)",
})
# 純數字型號（7300/9200…）若前後緊接金額語彙就不是型號，避免把「7300 元」誤判成型號。
_MODEL_AMOUNT_CTX = re.compile(r"[\d,]+\s*(元|塊|台幣|新台幣)")


def _known_model_pattern(model: str) -> re.Pattern[str]:
    """把型號編成**詞界感知**的 regex。

    不用子字串比對的理由：`TX` / `Rose` / `Alpha` 這種短或像單字的型號，子字串比對會在
    一般英文詞裡誤命中（誤判→無謂 regen→甚至誤轉真人）。改為要求前後不是英數字元，
    並容許型號內的分隔符（`AI-88` ≡ `AI 88` ≡ `AI88`）。
    """
    parts = [re.escape(c) for c in model if c not in " -"]
    body = r"[\s\-]?".join(parts)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


_KNOWN_MODEL_RES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (m, _known_model_pattern(m)) for m in sorted(_KNOWN_MODELS)
)

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


def _norm(s: str) -> str:
    """型號正規化：大寫、去空白與連字號（`AI-88` 與 `ai 88` 視為同一型號）。"""
    return s.upper().replace(" ", "").replace("-", "")


def _codes(text: str) -> set[str]:
    """抽出文中的具體型號：①regex 形狀（AS701 類）②知識庫已知型號清單。

    兩路併用的理由見 `_KNOWN_MODELS` 註解——regex 只涵蓋單一品牌的命名習慣。
    """
    t = text or ""
    found = {_norm(m.group(1)) for m in _MODEL_CODE.finditer(t)}

    # 已知型號：詞界感知比對。純數字型號（7300/9200…）若該處其實是金額（「7300 元」）
    # 就不算型號 —— 以字元區間重疊判定，避免同句其他位置的金額誤殺真型號。
    amount_spans = [m.span() for m in _MODEL_AMOUNT_CTX.finditer(t)]
    for model, pattern in _KNOWN_MODEL_RES:
        for hit in pattern.finditer(t):
            s, e = hit.span()
            if any(s < ae and as_ < e for as_, ae in amount_spans):
                continue  # 命中位置落在金額字串內 → 是金額不是型號
            found.add(_norm(model))
            break
    return found


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


# CR-0201 D3(b)：宣稱看到影像內容的字樣。**刻意收窄**——
# 只留「幾乎不可能在無圖語境自然出現」的說法。
#
# 被排除的候選與理由：「我看到」「看起來是」在故障排除對話裡每天都會出現
# （「看起來是電池沒電」），無條件納入會把大量正常文字對話推去人工。
# 違規的終局是把客人推給真人，誤判成本很高，所以寧可漏抓也不誤傷。
_VISION_CLAIM_MARKERS: tuple[str, ...] = (
    "照片中", "照片裡", "圖片中", "圖片裡", "圖中",
    "照片顯示", "圖片顯示", "從照片", "從圖片", "照片上",
)


# 通道層注入「本輪有照片」的穩定標記。定義在守衛這一側是刻意的：
# 偵測契約由使用者（guard）擁有，通道只是照著產生，避免措辭一改就悄悄失效。
# 照片被剝除後（CR-0201），這是 loop 唯一還能知道「本輪有照片」的線索。
PHOTO_TURN_SENTINEL = "[系統事實] 客人本輪傳了"


def turn_had_photo(customer_text: str) -> bool:
    """從客人訊息文字判定本輪是否附了照片（配合 PHOTO_TURN_SENTINEL）。"""
    return PHOTO_TURN_SENTINEL in (customer_text or "")


def vision_claim_violation(reply: str, *, has_media: bool) -> bool:
    """本 turn 有照片、且回覆宣稱看到照片內容 → 違規（合約紅線 SOW-2.1(4)）。

    **contextual 判定**：`has_media=False` 時一律不判。理由是純文字對話裡
    「照片中」這類字樣要嘛是客人自己提到照片、要嘛是模型幻覺，兩者都不是
    「AI 解讀了影像」——而後者已由 nightly 的 K8 forbidden eval 覆蓋
    （`agent/scripts/forbidden_eval.py` 的 image_moderation 題組）。
    做法與該檔一致：只在 `expect == "no_vision"` 的情境下套用，不是新發明。

    這條的價值不在攔截（前兩道 gate 已讓模型物理上看不到影像），
    而在**提供 runtime 的 violation 計數點** —— NFR-Sec-009 / NFR-Comp-003
    要求 violation count = 0 且需可稽核，沒有計數點就無從舉證。
    """
    if not has_media:
        return False
    return any(m in (reply or "") for m in _VISION_CLAIM_MARKERS)


def guard_violations(
    reply: str, customer_text: str, *, escalated: bool, has_media: bool = False,
) -> list[str]:
    """回傳違規原因清單（空＝通過）。

    has_media：本 turn 客人是否傳了照片。預設 False＝維持既有呼叫端行為不變
    （CR-0201 新增；只影響 vision_claim 這一條）。
    """
    out: list[str] = []
    if price_violation(reply, escalated=escalated):
        out.append("price_utterance")
    codes = unsourced_model_codes(reply, customer_text)
    if codes:
        out.append("unsourced_model:" + ",".join(codes[:5]))
    if claimed_transfer_violation(reply, escalated=escalated):
        out.append("claimed_transfer_without_tool")
    if vision_claim_violation(reply, has_media=has_media):
        out.append("vision_claim_without_capability")
    return out
