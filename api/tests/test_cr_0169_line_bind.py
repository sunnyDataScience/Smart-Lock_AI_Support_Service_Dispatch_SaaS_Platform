"""CR-0169 師傅 LINE 推播 — 純函式測試(無 DB/無外呼)。

綁定/推播全鏈另以 live E2E 驗證(雙庫容器環境;見 CR-0169 §7/§10)。
"""

import base64
import hashlib
import hmac

import pytest

import services.technician_line_service as tls
from core import line_uid_crypto
from routers.technician_line import _BIND_CODE_RE, _verify_line_signature
from services.technician_line_service import (
    _BIND_ATTEMPT_MAX,
    _bind_attempt_ok,
    _bind_attempts,
    _hash_code,
    _wo_summary,
    bind_by_code,
)


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


# ── R3: 綁定碼枚舉限流(_bind_attempt_ok 純函式) ──────────────────────────────

def test_bind_attempt_rate_limit():
    """同一 line_user_id 於 window 內 MAX 次內放行、第 MAX+1 次拒(擋枚舉搶綁)。"""
    _bind_attempts.clear()
    uid = "Uenum"
    for _ in range(_BIND_ATTEMPT_MAX):
        assert _bind_attempt_ok(uid) is True
    assert _bind_attempt_ok(uid) is False
    _bind_attempts.clear()


def test_bind_attempt_window_evicts(monkeypatch):
    """過 window 後舊嘗試逐出、重新放行(以 fake time 控制)。"""
    _bind_attempts.clear()

    class _FakeTime:
        def __init__(self):
            self.t = 1000.0

        def monotonic(self):
            return self.t

    ft = _FakeTime()
    monkeypatch.setattr(tls, "time", ft)
    uid = "Uwin"
    for _ in range(_BIND_ATTEMPT_MAX):
        assert _bind_attempt_ok(uid) is True
    assert _bind_attempt_ok(uid) is False
    ft.t += tls._BIND_ATTEMPT_WINDOW_SEC + 1  # 時間跳過 window
    assert _bind_attempt_ok(uid) is True
    _bind_attempts.clear()


def test_bind_attempt_empty_source_not_limited():
    """無 source(空字串 line_user_id)一律放行,不限流。"""
    _bind_attempts.clear()
    for _ in range(_BIND_ATTEMPT_MAX + 3):
        assert _bind_attempt_ok("") is True
    _bind_attempts.clear()


def test_bind_attempt_per_source_isolated():
    """不同 line_user_id 各自獨立計數,互不影響。"""
    _bind_attempts.clear()
    for _ in range(_BIND_ATTEMPT_MAX):
        _bind_attempt_ok("UA")
    assert _bind_attempt_ok("UA") is False  # UA 已達上限
    assert _bind_attempt_ok("UB") is True   # UB 不受影響
    _bind_attempts.clear()


# ── R4: 換綁自動解除他技師舊綁(mock conn,不碰真 DB) ────────────────────────

class _FakeCur:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many

    async def fetchone(self):
        return self._one

    async def fetchall(self):
        return self._many or []


@pytest.mark.asyncio
async def test_bind_by_code_rebind_unbinds_previous_tech(monkeypatch):
    """R4: 同一 line_user_id 換綁新技師時,自動解除舊技師綁定(避免派工推錯人)。"""
    _bind_attempts.clear()
    executed: list[tuple] = []

    class _FakeConn:
        async def execute(self, sql, params=None):
            executed.append((sql, params))
            if sql.startswith("SELECT c.id"):
                return _FakeCur(one=("code-1", "tech-NEW", "師傅B"))
            if "SET line_user_id = NULL" in sql:
                return _FakeCur(many=[("tech-OLD",)])  # 該 uid 原綁在 tech-OLD
            return _FakeCur()

    async def _fake_conn():
        return _FakeConn()

    monkeypatch.setattr(tls.db_module, "require_tech_conn", _fake_conn)

    res = await bind_by_code(line_user_id="Ushared", code="123456")
    assert res == {"technician_id": "tech-NEW", "name": "師傅B"}

    # 有發出「只解他人(id <> 新技師)」的 dup-unbind UPDATE
    unbind = [(s, p) for s, p in executed
              if "SET line_user_id = NULL" in s and "id <> " in s]
    assert unbind, "換綁應先發出 dup-unbind UPDATE"
    _, params = unbind[0]
    # CR-0173:dup-unbind 改以 bidx 等值查(+ 明文過渡雙軌)→ (bidx, line_user_id, tech)
    assert params == (
        line_uid_crypto.blind_index("Ushared"), "Ushared", "tech-NEW",
    )  # 解除綁到同 uid 但非新技師者
    _bind_attempts.clear()
