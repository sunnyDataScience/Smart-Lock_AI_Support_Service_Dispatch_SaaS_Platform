"""reply_guard 純函式單測(ADR-025/CR-0152——出口 guard 判定邏輯)。"""

from __future__ import annotations

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
