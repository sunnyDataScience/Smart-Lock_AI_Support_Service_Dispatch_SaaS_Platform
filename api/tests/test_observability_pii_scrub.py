"""OTel PII scrubbing 單元測試（25_Monitoring §3 硬性／2026-07-10 架構稽核補）。

scrub_text 為純函式（無 otel 依賴）：電話/email/地址遮蔽、LINE uid 雜湊化、
token 參數遮蔽；非 PII 原樣。_scrub_span_attributes 以 stub span 驗就地遮蔽。
"""
from __future__ import annotations

import hashlib

import pytest

from core.observability import _scrub_span_attributes, scrub_text

pytestmark = pytest.mark.unit


class TestScrubText:
    def test_line_uid_hashed_deterministic(self):
        uid = "U" + "ab12" * 8
        expect = "U#" + hashlib.sha256(uid.encode()).hexdigest()[:12]
        out = scrub_text(f"push to {uid} done")
        assert uid not in out
        assert expect in out
        # 同 uid 雜湊一致（保留關聯性）
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
            "http://x/realtime/rbac?access_token=eyJhbGciOi.abc&tenant_id=t1")
        assert "eyJhbGciOi" not in out
        assert "access_token=[TOKEN]" in out
        assert "tenant_id=t1" in out  # 非憑證參數保留

    def test_non_pii_untouched(self):
        s = "GET /tenants/00000000-0000-0000-0000-000000000001/work-orders 200 OK"
        assert scrub_text(s) == s


class _StubAttrs(dict):
    pass


class _StubSpan:
    def __init__(self, attrs):
        self._attributes = attrs


class TestScrubSpanAttributes:
    def test_scrubs_str_and_tuple_values_in_place(self):
        span = _StubSpan(_StubAttrs({
            "http.url": "http://x/cb?access_token=secret123",
            "customer.phone": "0912345678",
            "tags": ("a", "0912345678"),
            "http.status_code": 200,
        }))
        _scrub_span_attributes(span)
        assert span._attributes["http.url"].endswith("access_token=[TOKEN]")
        assert span._attributes["customer.phone"] == "[PHONE]"
        assert span._attributes["tags"] == ("a", "[PHONE]")
        assert span._attributes["http.status_code"] == 200

    def test_never_raises_on_weird_span(self):
        _scrub_span_attributes(object())  # 無 _attributes
        _scrub_span_attributes(_StubSpan(None))
