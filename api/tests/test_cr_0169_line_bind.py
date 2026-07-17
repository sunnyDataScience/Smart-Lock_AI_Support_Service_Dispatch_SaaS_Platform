"""CR-0169 師傅 LINE 推播 — 純函式測試(無 DB/無外呼)。

綁定/推播全鏈另以 live E2E 驗證(雙庫容器環境;見 CR-0169 §7/§10)。
"""

import base64
import hashlib
import hmac

from routers.technician_line import _BIND_CODE_RE, _verify_line_signature
from services.technician_line_service import _hash_code, _wo_summary


def test_bind_code_regex():
    assert _BIND_CODE_RE.match("123456")
    assert _BIND_CODE_RE.match("  123456  ")  # 前後空白容忍
    assert not _BIND_CODE_RE.match("12345")
    assert not _BIND_CODE_RE.match("1234567")
    assert not _BIND_CODE_RE.match("abc123")
    assert not _BIND_CODE_RE.match("你好 123456")  # 夾雜文字不算綁定碼


def test_hash_code_deterministic_and_not_plaintext():
    h = _hash_code("123456")
    assert h == _hash_code("123456")
    assert "123456" not in h
    assert len(h) == 64  # sha256 hex


def test_verify_line_signature(monkeypatch):
    secret = "test-line-secret"
    monkeypatch.setenv("PLATFORM_LINE_CHANNEL_SECRET", secret)
    body = b'{"events":[]}'
    good = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode("ascii")
    assert _verify_line_signature(body, good) is True
    assert _verify_line_signature(body, "bad-signature") is False
    assert _verify_line_signature(b"tampered", good) is False
    assert _verify_line_signature(body, None) is False


def test_verify_line_signature_rejects_when_secret_missing(monkeypatch):
    """未配置 secret 時一律拒(避免裸 webhook 端點)。"""
    monkeypatch.delenv("PLATFORM_LINE_CHANNEL_SECRET", raising=False)
    assert _verify_line_signature(b"{}", "anything") is False


def test_wo_summary_minimal_no_pii():
    """推播內容最小化(CIA §4):絕不含客戶姓名/地址/電話。"""
    wo = {
        "id": "a9cf9f30-403b-46bc-965f-ed35feab9eac",
        "document_number": "TP-000009",
        "district": "台北市大安區",
        "brand": "Chatlock",
        "model": "A90",
        # 以下欄位即使傳入也不得出現在摘要
        "customer_name": "王大明",
        "customer_phone": "0911222333",
        "customer_address": "台北市大安區某路 1 號 5F",
    }
    text = _wo_summary(wo)
    assert "台北市大安區" in text and "Chatlock A90" in text and "TP-000009" in text
    assert "王大明" not in text
    assert "0911222333" not in text
    assert "某路" not in text


def test_wo_summary_fallbacks():
    assert "新工單" in _wo_summary({"id": "12345678-0000"})  # 無區域/型號
    assert "12345678" in _wo_summary({"id": "12345678-0000"})  # 單號縮寫 fallback
