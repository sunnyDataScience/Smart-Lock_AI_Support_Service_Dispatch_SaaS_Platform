"""refinery 可觀測性測試（CR-0156 / ADR-007 補課）。

scrub_text 為純函式（無 otel 依賴）：電話/email/地址遮蔽、LINE uid 雜湊化、
token 參數遮蔽；非 PII 原樣。_scrub_span_attributes 以 stub span 驗就地遮蔽。
setup_observability：env 未配置＝no-op（回 False、零行為變化）；配置了但套件缺
/初始化失敗＝降級不 raise。
"""
from __future__ import annotations

import hashlib

from refinery.observability import (
    _scrub_span_attributes,
    observability_enabled,
    scrub_text,
    setup_observability,
)


# ── scrub_text 純函式 ────────────────────────────────────────────────────────

class TestScrubText:
    def test_line_uid_hashed_deterministic(self):
        uid = "U" + "ab12" * 8
        expect = "U#" + hashlib.sha256(uid.encode()).hexdigest()[:12]
        out = scrub_text(f"push to {uid} done")
        assert uid not in out
        assert expect in out
        # 同 uid 雜湊一致（保留關聯性不留身分）
        assert scrub_text(uid) == expect

    def test_mobile_phone_masked(self):
        assert scrub_text("客戶電話 0912345678") == "客戶電話 [PHONE]"
        assert scrub_text("call +886-912-345-678") == "call [PHONE]"
        assert "0912-345-678" not in scrub_text("0912-345-678")

    def test_landline_masked(self):
        assert scrub_text("市話 02-27123456") == "市話 [PHONE]"

    def test_email_masked(self):
        assert scrub_text("寄到 test@lock-ai.com 了") == "寄到 [EMAIL] 了"

    def test_tw_address_masked(self):
        out = scrub_text("地址：台北市大安區和平東路二段106號")
        assert "和平東路" not in out
        assert "[ADDR]" in out

    def test_token_query_param_masked(self):
        out = scrub_text(
            "http://x/api/drafts?access_token=eyJhbGciOi.abc&status=pending_review")
        assert "eyJhbGciOi" not in out
        assert "access_token=[TOKEN]" in out
        assert "status=pending_review" in out  # 非憑證參數保留

    def test_non_pii_untouched(self):
        s = "GET /api/drafts/42 200 OK"
        assert scrub_text(s) == s


# ── _scrub_span_attributes（stub span，無 otel 依賴）───────────────────────

class _StubSpan:
    def __init__(self, attrs):
        self._attributes = attrs


class TestScrubSpanAttributes:
    def test_scrubs_str_and_tuple_values_in_place(self):
        span = _StubSpan({
            "http.url": "http://x/cb?access_token=secret123",
            "customer.phone": "0912345678",
            "tags": ("a", "0912345678"),
            "http.status_code": 200,
        })
        _scrub_span_attributes(span)
        assert span._attributes["http.url"].endswith("access_token=[TOKEN]")
        assert span._attributes["customer.phone"] == "[PHONE]"
        assert span._attributes["tags"] == ("a", "[PHONE]")
        assert span._attributes["http.status_code"] == 200

    def test_never_raises_on_weird_span(self):
        _scrub_span_attributes(object())  # 無 _attributes
        _scrub_span_attributes(_StubSpan(None))


# ── setup_observability：opt-in / 降級語意 ──────────────────────────────────

class TestSetupObservability:
    def test_noop_without_endpoint(self, monkeypatch):
        """未設 OTLP endpoint → setup 回 False（no-op，單機行為不變）。"""
        from fastapi import FastAPI

        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        app = FastAPI()
        assert setup_observability(app) is False
        assert observability_enabled() is False

    def test_failsoft_on_endpoint_set(self, monkeypatch):
        """設了 endpoint 但套件缺（otel 為 optional extra，未裝）/初始化失敗
        → 降級回 bool，關鍵是不 raise（不癱瘓服務）。"""
        from fastapi import FastAPI

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid:4317")
        app = FastAPI()
        result = setup_observability(app)
        assert isinstance(result, bool)
