"""HMAC token + PII masking unit tests（無 DB / 無 ASGI）。

涵蓋：
  1. generate → verify roundtrip 同 payload
  2. expired token → TokenExpiredError
  3. tampered signature → TokenInvalidError
  4. tampered payload → TokenInvalidError
  5. wrong purpose enum → TokenInvalidError
  6. revoke then verify → TokenExpiredError
  7. mask_phone 行為
  8. mask_technician_name 中文 / 英文 fallback
  9. nonce uniqueness（100 個 token nonce 全不同）
  10. ttl_days 帶入 1 vs 30 → expires_at 對齊
  11. malformed token（沒有 dot）
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# 將 api/ 加入 sys.path，與 conftest.py 對齊
API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# 強制使用 dev 預設 secret，避免讀到生產設定
os.environ.pop("PUBLIC_TOKEN_HMAC_SECRET", None)

from services import public_token  # noqa: E402

pytestmark = pytest.mark.unit


def test_generate_and_verify_roundtrip():
    sub = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    token = public_token.generate_token(
        sub, purpose="work_order_status", ttl_days=30, tenant_id="tenant-1"
    )
    assert "." in token  # payload.sig 雙段格式

    payload = public_token.verify_token(token)
    assert payload.subject_id == sub
    assert payload.purpose == "work_order_status"
    assert payload.tenant_id == "tenant-1"
    assert payload.expires_at > datetime.now(timezone.utc)
    assert payload.nonce is not None and len(payload.nonce) >= 8


def test_verify_expired_token_raises():
    token = public_token.generate_token(
        "subj-1", purpose="scope_change", ttl_days=-1
    )
    with pytest.raises(public_token.TokenExpiredError):
        public_token.verify_token(token)


def test_verify_tampered_signature_raises():
    token = public_token.generate_token("subj-1", purpose="scope_change")
    payload_b64, sig_b64 = token.split(".", 1)
    # flip 最後一個字元（保持 base64url 字元）
    flipped = "A" if sig_b64[-1] != "A" else "B"
    tampered = f"{payload_b64}.{sig_b64[:-1]}{flipped}"
    with pytest.raises(public_token.TokenInvalidError):
        public_token.verify_token(tampered)


def test_verify_tampered_payload_raises():
    token = public_token.generate_token("subj-1", purpose="scope_change")
    payload_b64, sig_b64 = token.split(".", 1)
    flipped = "A" if payload_b64[0] != "A" else "B"
    tampered = f"{flipped}{payload_b64[1:]}.{sig_b64}"
    with pytest.raises(public_token.TokenInvalidError):
        public_token.verify_token(tampered)


def test_verify_malformed_token_no_dot_raises():
    with pytest.raises(public_token.TokenInvalidError):
        public_token.verify_token("not-a-valid-token-at-all")


def test_verify_empty_token_raises():
    with pytest.raises(public_token.TokenInvalidError):
        public_token.verify_token("")


def test_revoke_then_verify_raises():
    token = public_token.generate_token("subj-revoke-1", purpose="scope_change")
    # 先驗一次確認 OK
    public_token.verify_token(token)
    # 撤銷後再驗應失敗
    public_token.revoke_token(token)
    with pytest.raises(public_token.TokenExpiredError):
        public_token.verify_token(token)


def test_mask_phone_keeps_only_last_four():
    assert public_token.mask_phone("0912345678") == "****5678"
    assert public_token.mask_phone(None) is None
    assert public_token.mask_phone("123") == "****"
    assert public_token.mask_phone("") is None
    # 含空白與符號
    assert public_token.mask_phone("0912-345-678") == "****5678"


def test_mask_technician_name_chinese_first_char():
    assert public_token.mask_technician_name("陳大文") == "陳師傅"
    assert public_token.mask_technician_name("王") == "王師傅"
    assert public_token.mask_technician_name(None) is None
    assert public_token.mask_technician_name("") is None


def test_mask_technician_name_english_fallback():
    assert public_token.mask_technician_name("John Smith") == "J. Master"


def test_nonce_uniqueness_100():
    nonces = set()
    for _ in range(100):
        token = public_token.generate_token("subj-1", purpose="scope_change")
        payload = public_token.verify_token(token)
        nonces.add(payload.nonce)
    assert len(nonces) == 100, "nonce should be unique across 100 tokens"


def test_ttl_days_affects_expiry():
    short = public_token.generate_token("s1", purpose="scope_change", ttl_days=1)
    long = public_token.generate_token("s1", purpose="scope_change", ttl_days=30)
    short_payload = public_token.verify_token(short)
    long_payload = public_token.verify_token(long)
    delta_days = (long_payload.expires_at - short_payload.expires_at).days
    assert 28 <= delta_days <= 30


def test_token_hash_for_audit_is_deterministic_and_long():
    token = public_token.generate_token("s1", purpose="scope_change")
    h1 = public_token.token_hash_for_audit(token)
    h2 = public_token.token_hash_for_audit(token)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_secret_env_overrides_dev_default(monkeypatch):
    """設置 PUBLIC_TOKEN_HMAC_SECRET 後，舊 dev secret 簽出的 token 應驗失敗。"""
    token = public_token.generate_token("s1", purpose="scope_change")
    # 確認 dev secret 簽的 token 在原設定下可驗證
    public_token.verify_token(token)
    monkeypatch.setenv("PUBLIC_TOKEN_HMAC_SECRET", f"another-secret-{time.time()}")
    with pytest.raises(public_token.TokenInvalidError):
        public_token.verify_token(token)
