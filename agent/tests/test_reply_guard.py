"""reply_guard 純函式單測(ADR-025/CR-0152——出口 guard 判定邏輯)。"""

from __future__ import annotations

import pytest

from lockcore.agent.reply_guard import (
    TRANSFER_FALLBACK,
    claimed_transfer_violation,
    guard_violations,
    price_violation,
    unsourced_model_codes,
)


class TestPriceViolation:
    def test_price_without_escalation_is_violation(self):
        assert price_violation("更換大約 NT$3,500 元", escalated=False)
        assert price_violation("工資約 1200 元", escalated=False)
        assert price_violation("$800 起", escalated=False)

    def test_price_with_escalation_allowed(self):
        assert not price_violation("報價約 NT$3500,已為您轉接專員確認", escalated=True)

    def test_no_price_ok(self):
        assert not price_violation("這部分為您轉接專員協助 🙏", escalated=False)
        assert not price_violation("電池約可用 12 個月", escalated=False)  # 數字+月 非價格


class TestUnsourcedModel:
    def test_model_not_mentioned_by_customer(self):
        out = unsourced_model_codes("您的 Yale YDM4109 支援指紋", "我家的鎖打不開")
        assert out == ["YDM4109"]

    def test_model_mentioned_by_customer_ok(self):
        assert unsourced_model_codes(
            "YDM4109 的重置孔在底部", "我的 YDM4109 怎麼恢復原廠") == []

    def test_separator_normalized(self):
        assert unsourced_model_codes("建議 SHP-DP609", "我用 SHP DP609") == []


class TestClaimedTransfer:
    """CR-0166 R0：say-do gap 兜底——嘴上說轉接、實際沒呼叫工具（K8 warranty_free 裁定）。"""

    def test_definitive_claim_without_tool_is_violation(self):
        assert claimed_transfer_violation(
            "關於保固年限，我將為您轉接專員協助處理，會有專員與您聯繫。", escalated=False)
        assert claimed_transfer_violation(
            "請提供品牌型號，我將協助您轉接給專員處理。", escalated=False)
        assert claimed_transfer_violation(
            "已為您轉接真人專員，請稍候。", escalated=False)

    def test_claim_with_actual_tool_call_ok(self):
        assert not claimed_transfer_violation(
            "已為您轉接真人專員，請稍候。", escalated=True)

    def test_offer_phrasing_is_not_violation(self):
        """提議句（需要我幫您轉接嗎）不強迫轉接——只攔確定式宣告。"""
        assert not claimed_transfer_violation(
            "如果需要，我可以幫您轉接真人專員，請問要嗎？", escalated=False)

    def test_guard_violations_includes_code(self):
        v = guard_violations(
            "我將為您轉接專員處理。", "保固可以免費嗎", escalated=False)
        assert "claimed_transfer_without_tool" in v


class TestGuardViolations:
    def test_clean_reply_passes(self):
        assert guard_violations("請問門鎖是哪個牌子呢?", "打不開", escalated=False) == []

    def test_combined_violations(self):
        v = guard_violations("您的 YDM4109 換鎖約 3500 元", "打不開", escalated=False)
        assert "price_utterance" in v
        assert any(x.startswith("unsourced_model:") for x in v)

    def test_transfer_fallback_itself_is_clean(self):
        """兜底話術自身必須永遠過 guard(不含數字/型號)。"""
        assert guard_violations(TRANSFER_FALLBACK, "", escalated=False) == []
        assert guard_violations(TRANSFER_FALLBACK, "", escalated=True) == []


# ── CR-0201 D3(b)：宣稱看到影像內容（contextual）─────────────────────────


def test_vision_claim_flagged_only_when_media_present():
    """有照片時宣稱看到內容 → 違規；同一句話在無照片語境下不判。"""
    from lockcore.agent.reply_guard import vision_claim_violation

    reply = "照片中可以看到面板已經裂開了"
    assert vision_claim_violation(reply, has_media=True) is True
    assert vision_claim_violation(reply, has_media=False) is False


def test_vision_claim_does_not_flag_normal_troubleshooting_language():
    """反向：故障排除的日常用語不可被誤判——違規的終局是把客人推去人工。

    「看起來是」「我看到」刻意**不在** marker 清單內（CR-0201 D3(b) 收窄決策）。
    """
    from lockcore.agent.reply_guard import vision_claim_violation

    for reply in (
        "看起來是電池沒電了,建議先換電池試試",
        "我看到您提到卡片刷不過,請問嗶聲有幾聲?",
        "根據您描述的狀況,面板應該是接觸不良",
        "請您拍一張門鎖正面的照片給我們,客服人員會協助查看",
    ):
        assert vision_claim_violation(reply, has_media=True) is False, f"誤判：{reply!r}"


def test_guard_violations_reports_vision_claim():
    """接進 guard_violations 主線，且預設參數不改變既有呼叫端行為。"""
    from lockcore.agent.reply_guard import guard_violations

    reply = "從照片判斷,您的鎖體已經變形"
    assert "vision_claim_without_capability" in guard_violations(
        reply, "門鎖壞了", escalated=False, has_media=True)
    # 未傳 has_media（既有呼叫端）→ 行為不變
    assert "vision_claim_without_capability" not in guard_violations(
        reply, "門鎖壞了", escalated=False)


# ── BR-Quote-002 規則 2、3：折扣 / 免費保固承諾（CR-0208 D1(a)）──────────
#
# 正典 04_SRS.md:449 要三條規則，此前只實作了 NTD 數字那條。
# 誤攔成本很高（違規的終局是把客人推去人工，NFR-Sec-006 要誤攔率 < 1%），
# 所以下面正反例並重——反例比正例更重要。


@pytest.mark.parametrize("reply", [
    "好的,這次維修可以幫您打八折",
    "沒問題,算您便宜一點",
    "我們可以免費幫您保固三年",
    "這個免費維修,不收費",
    "給您一個折扣碼,安裝可以省一點",
    "保證終身保固,不用錢",
])
def test_concession_promise_flagged(reply):
    """AI 答應讓利 → 必須攔下（BR-Quote-002 規則 2、3）。"""
    from lockcore.agent.reply_guard import concession_promise_violation

    assert concession_promise_violation(reply, escalated=False) is True, f"漏抓：{reply!r}"


@pytest.mark.parametrize("reply", [
    "折扣的部分我無法決定,會請專員與您聯繫",
    "優惠方案需要由專員為您確認,我先幫您登記",
    "這是否在保固範圍內要看實際狀況,實際費用以現場報價為準",
    "免費保固的條件我不便判斷,轉由客服人員說明",
    "請問門鎖是完全沒反應,還是有嗶聲?",
    "建議您先換電池試試看,這個很常見",
    "保固期限一般是原廠公告為準,詳細我請專員確認",
])
def test_concession_guard_does_not_flag_compliant_replies(reply):
    """反向：合規回覆不可被誤攔。

    這批全都**提到**折扣/保固/免費，但語意是「我不能決定，轉專員」——
    正是我們要的行為。裸關鍵字比對會把這些全判成違規。
    """
    from lockcore.agent.reply_guard import concession_promise_violation

    assert concession_promise_violation(reply, escalated=False) is False, f"誤攔：{reply!r}"


def test_concession_guard_exempt_when_escalated():
    """已轉真人時不判——與 price_violation 同一套豁免邏輯。"""
    from lockcore.agent.reply_guard import concession_promise_violation

    assert concession_promise_violation("可以幫您打八折", escalated=True) is False


def test_guard_violations_reports_concession_promise():
    """接進 guard_violations 主線。"""
    from lockcore.agent.reply_guard import guard_violations

    assert "concession_promise" in guard_violations(
        "沒問題,免費幫您保固", "保固免費吧", escalated=False)
