"""refinery Casdoor OIDC alg 路由測試（2.3.2 遺留銷案）——純驗證邏輯，不碰 DB。

自鑄 RSA keypair 簽 RS256 token 打 `service._decode`，驗三鐵律：
  1. RS256＋OIDC 已配置 → 正規化 payload（sub=smartlock_user_id）
  2. OIDC 未配置時 RS256 一律 401（不誤入 HS256 路徑）
  3. alg-confusion 擋住：拿公鑰當 HS256 secret 簽的 token 過不了
HS256 interim 路徑回歸：既有 secret 簽的 token 照常可解。
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

crypto = pytest.importorskip("cryptography")  # jose RS256 需 cryptography backend
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from jose import jwt  # noqa: E402

from refinery import oidc, service  # noqa: E402

_TID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


@pytest.fixture()
def oidc_env(keypair, monkeypatch):
    _, pub = keypair
    monkeypatch.setenv("CASDOOR_ENDPOINT", "http://casdoor.test:8000")
    monkeypatch.setenv("CASDOOR_CLIENT_ID", "refinery-client")
    monkeypatch.setenv("CASDOOR_JWT_PUBLIC_KEY", pub)


def _rs256_token(priv: str, *, props: dict | None = None) -> str:
    claims = {
        "iss": "http://casdoor.test:8000",
        "aud": "refinery-client",
        "sub": "casdoor-native-sub",
        "jti": "j-1",
        "properties": props if props is not None else {
            "smartlock_user_id": "u-42",
            "smartlock_role": "reviewer",
            "tenant_id": _TID,
        },
    }
    return jwt.encode(claims, priv, algorithm="RS256")


def test_rs256_normalized(keypair, oidc_env):
    priv, _ = keypair
    payload = service._decode(_rs256_token(priv))
    assert payload["sub"] == "u-42"  # 映射 users.id，非 Casdoor 原生 sub
    assert payload["role"] == "reviewer"
    assert payload["tenant_id"] == _TID
    assert payload["type"] == "access"  # require_reviewer 下游檢查零改動


def test_rs256_rejected_when_oidc_unconfigured(keypair, monkeypatch):
    for k in ("CASDOOR_ENDPOINT", "CASDOOR_CLIENT_ID", "CASDOOR_JWT_PUBLIC_KEY"):
        monkeypatch.delenv(k, raising=False)
    priv, _ = keypair
    with pytest.raises(HTTPException) as ei:
        service._decode(_rs256_token(priv))
    assert ei.value.status_code == 401


def test_rs256_missing_mapping_rejected(keypair, oidc_env):
    priv, _ = keypair
    with pytest.raises(HTTPException) as ei:
        service._decode(_rs256_token(priv, props={}))  # 未 bootstrap 映射
    assert ei.value.status_code == 401


def test_alg_confusion_blocked(keypair, oidc_env, monkeypatch):
    """拿 RS256 公鑰當 HS256 secret 簽 → HS256 路徑只認 API_JWT_SECRET_KEY，必 401。

    jose 自身拒絕以 PEM 當 HMAC secret 簽章，故手工 HMAC 鑄造（模擬真攻擊者）。
    """
    import base64
    import hashlib
    import hmac
    import json

    def _b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    _, pub = keypair
    monkeypatch.setenv("API_JWT_SECRET_KEY", "kr-test-secret")
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": "u-42", "role": "admin", "tenant_id": _TID,
                            "type": "access"}).encode())
    sig = _b64(hmac.new(pub.encode(), f"{header}.{body}".encode(),
                        hashlib.sha256).digest())
    with pytest.raises(HTTPException) as ei:
        service._decode(f"{header}.{body}.{sig}")
    assert ei.value.status_code == 401


def test_hs256_interim_still_works(monkeypatch):
    monkeypatch.setenv("API_JWT_SECRET_KEY", "kr-test-secret")
    tok = jwt.encode({"sub": "u-1", "role": "admin", "tenant_id": _TID,
                      "type": "access"}, "kr-test-secret", algorithm="HS256")
    payload = service._decode(tok)
    assert payload["sub"] == "u-1" and payload["role"] == "admin"


def test_garbage_token_401():
    with pytest.raises(HTTPException) as ei:
        service._decode("not-a-jwt")
    assert ei.value.status_code == 401
