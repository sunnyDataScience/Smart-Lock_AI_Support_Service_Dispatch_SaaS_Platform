"""CR-0166 R1-8：PII 遮蔽共用工具（含 audit payload 遮蔽）。"""

from __future__ import annotations

from core.pii_scrub import scrub_audit_payload, scrub_audit_value, scrub_text


def test_scrub_text_full():
    """log/span 全遮蔽（含地址）。"""
    s = scrub_text("客戶 a@b.com 電話 0912345678 住台北市大安區忠孝東路100號")
    assert "[EMAIL]" in s and "[PHONE]" in s and "[ADDR]" in s
    assert "a@b.com" not in s and "0912345678" not in s


def test_national_id_masked():
    assert scrub_text("身分證 A123456789 已核") == "身分證 [ID] 已核"
    assert scrub_audit_value("A123456789") == "[ID]"


def test_line_uid_hashed():
    out = scrub_text("U" + "a" * 32)
    assert out.startswith("U#") and len(out) == len("U#") + 12


def test_audit_value_keeps_address():
    """audit 變體不遮地址（保稽核證據力），但遮 email/電話/身分證。"""
    v = scrub_audit_value("退款理由：客戶 x@y.com 於台北市信義區松高路11號 爭議")
    assert "[EMAIL]" in v
    assert "台北市信義區松高路11號" in v  # 地址保留


def test_audit_payload_recursive():
    payload = {
        "reason": "聯絡 09 12345678 的客戶",  # 注意此格式不完全匹配電話 regex
        "contact": {"email": "z@w.com", "national_id": "B234567890"},
        "items": ["phone 0912345678", "ok"],
    }
    out = scrub_audit_payload(payload)
    assert out["contact"]["email"] == "[EMAIL]"
    assert out["contact"]["national_id"] == "[ID]"
    assert "0912345678" not in out["items"][0]
    assert out["items"][1] == "ok"


def test_non_string_passthrough():
    assert scrub_audit_value(123) == 123
    assert scrub_audit_payload({"n": 5, "b": True}) == {"n": 5, "b": True}
