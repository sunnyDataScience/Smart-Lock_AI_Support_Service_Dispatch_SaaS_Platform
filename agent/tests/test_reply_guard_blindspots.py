"""reply_guard 盲點回歸（2026-07-27）。

以語料實測發現的兩個確定性 guard 破口：

1. **價格只認阿拉伯數字** —— 「一千五百元」「兩千塊」「壹仟元」等中文數字報價完全不攔。
   紅線是「報價一律轉真人」，中文客服語境用中文數字報價相當自然 → 破口實際會被踩到。
2. **型號只認 Dormakaba 命名形狀** —— regex 要 ≥2 大寫字母＋≥3 位數字，故 Chatlock `A90`
   （1 字母+2 數字）、Milre `6500F`（數字開頭）、Philips `7300`（純數字）一律漏判，
   grounding guard 等於只守一個品牌。改以知識庫實際型號清單精確比對。

本檔同時守「型號清單 vs 知識庫」不漂移——新增產品卻忘了更新常數時，測試會紅。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lockcore.agent.reply_guard import (
    _KNOWN_MODELS,
    _norm,
    price_violation,
    unsourced_model_codes,
)


# ── 價格：中文數字亦須攔截 ────────────────────────────────────────────
_PRICE_BLOCK = [
    ("中文數字-千", "維修費用大約是一千五百元"),
    ("中文數字-兩千", "大概兩千塊左右"),
    ("中文數字-百", "換鎖芯三百元有找"),
    ("國字大寫", "工資壹仟元"),
    ("阿拉伯數字", "維修費用 1500 元"),
    ("NT$ 格式", "費用 NT$ 2,000 起"),
]
_PRICE_PASS = [
    ("轉真人話術", "費用需由專員報價，我先為您轉接"),
    ("電池規格", "請用 9V 方型電池臨時供電"),
    ("型號含數字", "您的鎖是 AS701 型號"),
    ("條件句含『萬一』", "萬一還是打不開，我們再安排師傅"),
    ("工作天", "大約需要三個工作天"),
    ("時間", "十分鐘後再試一次"),
]


@pytest.mark.parametrize("label,text", _PRICE_BLOCK, ids=[c[0] for c in _PRICE_BLOCK])
def test_price_violation_blocks(label, text):
    assert price_violation(text, escalated=False) is True, f"[{label}] 報價未被攔截：{text}"


@pytest.mark.parametrize("label,text", _PRICE_PASS, ids=[c[0] for c in _PRICE_PASS])
def test_price_violation_no_false_positive(label, text):
    assert price_violation(text, escalated=False) is False, f"[{label}] 誤攔非報價：{text}"


def test_price_allowed_when_already_escalated():
    """已轉真人時允許話術帶金額語境（既有行為，不得因本次放寬而改變）。"""
    assert price_violation("費用 1500 元", escalated=True) is False


# ── 型號：知識庫實際命名都要抓得到 ───────────────────────────────────
_MODEL_FLAG = [
    ("Chatlock A90（1字母2數字）", "您的 A90 需要重設", "我家鎖打不開"),
    ("Milre 6500F（數字開頭）", "Milre 6500F 的操作是…", "我家鎖打不開"),
    ("Philips 7300（純數字）", "Philips 7300 支援指紋", "我家鎖打不開"),
    ("Chatlock AI-88（含連字號）", "AI-88 的設定方式", "我家鎖打不開"),
    ("Dormakaba AS701（原 regex 涵蓋）", "建議確認 AS701 的設定", "我家鎖打不開"),
]
_MODEL_PASS = [
    ("客戶已提過則不算幻覺", "AS701 的設定方式", "我的鎖是 AS701"),
    ("金額不是型號", "維修約 7300 元", "我家鎖打不開"),
    ("無型號", "請先更換電池再試一次", "我家鎖打不開"),
]


@pytest.mark.parametrize("label,reply,cust", _MODEL_FLAG, ids=[c[0] for c in _MODEL_FLAG])
def test_unsourced_model_detected(label, reply, cust):
    assert unsourced_model_codes(reply, cust), f"[{label}] 未溯源型號漏判：{reply}"


@pytest.mark.parametrize("label,reply,cust", _MODEL_PASS, ids=[c[0] for c in _MODEL_PASS])
def test_unsourced_model_no_false_positive(label, reply, cust):
    assert unsourced_model_codes(reply, cust) == [], f"[{label}] 誤判為未溯源型號：{reply}"


# ── 詞界感知：短／像單字的型號（TX / Rose / Alpha）不得在一般文字中誤命中 ──
_BOUNDARY_CASES = [
    ("英文詞含 TX 子字串", "請確認 NEXTX 韌體版本", False),
    ("rosegold 非型號", "玫瑰金 rosegold 面板", False),
    ("alphanumeric 非型號", "請設定 alphanumeric 密碼", False),
    ("真的提到 TX", "3E TX 的操作方式", True),
    ("真的提到 Rose", "Dormakaba Rose 系列", True),
    ("真的提到 Alpha", "Philips Alpha 支援指紋", True),
    ("同句有金額也有真型號", "7300 這台維修約 1500 元", True),
    ("純金額不算型號", "維修約 7300 元", False),
]


@pytest.mark.parametrize("label,text,expected", _BOUNDARY_CASES,
                         ids=[c[0] for c in _BOUNDARY_CASES])
def test_known_model_matching_is_boundary_aware(label, text, expected):
    """子字串比對會讓 TX/Rose/Alpha 在英文詞裡誤命中 → 無謂 regen 甚至誤轉真人。"""
    got = bool(unsourced_model_codes(text, "我家鎖打不開"))
    assert got is expected, f"[{label}] 詞界判定錯誤（得 {got}）：{text}"


def test_known_models_in_sync_with_knowledge_base():
    """`_KNOWN_MODELS` 必須涵蓋知識庫 references/{Brand}/*.md 的所有型號。

    WHY：清單是手維護常數（reply_guard 刻意保持純函式、不做 I/O）。新增產品卻忘了
    更新常數時，該型號的幻覺就守不住 —— 本測試把「記得更新」變成 CI 的事。
    只檢查「知識庫有但常數沒有」（缺漏＝守不住）；常數多列不算錯（型號可能已下架）。
    """
    refs = Path(__file__).resolve().parents[1] / "lockcore" / "skills" / \
        "locksmith-product-knowledge" / "references"
    assert refs.is_dir(), f"知識庫 references 不存在：{refs}"

    known = {_norm(m) for m in _KNOWN_MODELS}
    missing: list[str] = []
    for brand_dir in sorted(refs.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name.startswith("_"):
            continue
        for md in sorted(brand_dir.glob("*.md")):
            model = md.stem
            if model.startswith("_"):
                continue
            # 非 ASCII 型號（如 Kaadas「藍寶堅尼3D人臉辨識」）不納入代碼比對——
            # 中文品名不會被誤認為型號代碼，且會與一般敘述衝突。
            if not model.isascii():
                continue
            if _norm(model) not in known:
                missing.append(f"{brand_dir.name}/{model}")

    assert not missing, (
        "知識庫有型號但 reply_guard._KNOWN_MODELS 未收錄（幻覺守不住）：\n  "
        + "\n  ".join(missing)
        + "\n→ 請同步更新 agent/lockcore/agent/reply_guard.py 的 _KNOWN_MODELS"
    )
