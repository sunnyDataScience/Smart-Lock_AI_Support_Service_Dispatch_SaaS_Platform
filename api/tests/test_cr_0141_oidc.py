"""CR-0141 Casdoor OIDC 雙驗(WBS 2.1.1 R1)。

- opt-in:CASDOOR_* 未配置 → 行為與舊版完全相同(壞 token 一律 401)
- RS256 驗簽 + iss/aud 校驗;claims 正規化(properties.smartlock_user_id → sub)
- 未映射帳號(缺 smartlock_user_id)拒絕——不可 fallback 到 Casdoor 原生 sub
- cookie fallback(ACT-01 地基):無 Authorization header 時讀 httpOnly cookie
- 下游不變:OIDC token 過 A2/A3 重查(停權帳號 403)
"""
from __future__ import annotations

import time
import uuid

import pytest
from jose import jwt
from starlette.requests import Request

import core.db as db_module
from core import oidc
from core.deps import _extract_bearer, get_current_user
from core.errors import ApiError

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
ENDPOINT = "http://casdoor.test:8005"
CLIENT_ID = "smartlock-portal-client"


@pytest.fixture(scope="module")
def rsa_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture()
def oidc_env(monkeypatch, rsa_keys):
    _, public_pem = rsa_keys
    monkeypatch.setenv("CASDOOR_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("CASDOOR_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("CASDOOR_JWT_PUBLIC_KEY", public_pem)


def _casdoor_token(private_pem: str, *, user_id: str | None = None, role: str = "admin",
                   tenant: str = TID, iss: str = ENDPOINT, aud: str = CLIENT_ID,
                   exp_delta: int = 3600, roles_list: list | None = None,
                   props_override: dict | None = None) -> str:
    now = int(time.time())
    props = {"tenant_id": tenant}
    if user_id:
        props["smartlock_user_id"] = user_id
    if role:
        props["smartlock_role"] = role
    if props_override is not None:
        props = props_override
    payload = {
        "iss": iss, "aud": aud, "sub": f"casdoor-native-{uuid.uuid4().hex[:8]}",
        "iat": now, "exp": now + exp_delta, "jti": str(uuid.uuid4()),
        "owner": "locksmart", "name": "tester",
        "properties": props,
    }
    if roles_list is not None:
        payload["roles"] = roles_list
    return jwt.encode(payload, private_pem, algorithm="RS256")


def _request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"smartlock_access_token={cookie}".encode())] if cookie else []
    return Request({"type": "http", "headers": headers, "method": "GET", "path": "/"})


# ── opt-in 邊界 ──────────────────────────────────────────────────────────────

def test_oidc_disabled_without_env(monkeypatch):
    for k in ("CASDOOR_ENDPOINT", "CASDOOR_CLIENT_ID", "CASDOOR_JWT_PUBLIC_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert oidc.oidc_enabled() is False


@pytest.mark.asyncio
async def test_garbage_token_401_unchanged_when_disabled(monkeypatch):
    for k in ("CASDOOR_ENDPOINT", "CASDOOR_CLIENT_ID", "CASDOOR_JWT_PUBLIC_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ApiError) as e:
        await get_current_user(_request(), "Bearer not-a-jwt")
    assert e.value.status_code == 401


# ── RS256 驗簽與 claims 正規化 ───────────────────────────────────────────────

def test_verify_ok_and_claims_mapping(oidc_env, rsa_keys):
    private_pem, _ = rsa_keys
    uid = str(uuid.uuid4())
    payload = oidc.verify_oidc_token(_casdoor_token(private_pem, user_id=uid))
    assert payload["sub"] == uid, "sub 必須是 smartlock_user_id 映射,非 Casdoor 原生 sub"
    assert payload["role"] == "admin" and payload["tenant_id"] == TID
    assert payload["type"] == "access"


def test_verify_rejects_wrong_aud_iss_expired(oidc_env, rsa_keys):
    private_pem, _ = rsa_keys
    uid = str(uuid.uuid4())
    for bad in (
        _casdoor_token(private_pem, user_id=uid, aud="other-client"),
        _casdoor_token(private_pem, user_id=uid, iss="http://evil.test"),
        _casdoor_token(private_pem, user_id=uid, exp_delta=-10),
    ):
        with pytest.raises(oidc.OIDCError):
            oidc.verify_oidc_token(bad)


def test_verify_rejects_unmapped_account(oidc_env, rsa_keys):
    private_pem, _ = rsa_keys
    with pytest.raises(oidc.OIDCError, match="smartlock_user_id"):
        oidc.verify_oidc_token(_casdoor_token(private_pem, user_id=None))


def test_role_fallback_to_native_roles(oidc_env, rsa_keys):
    private_pem, _ = rsa_keys
    uid = str(uuid.uuid4())
    token = _casdoor_token(
        private_pem, user_id=uid, role="",
        props_override={"smartlock_user_id": uid, "tenant_id": TID},
        roles_list=[{"name": "reviewer"}],
    )
    assert oidc.verify_oidc_token(token)["role"] == "reviewer"


# ── get_current_user 雙驗整合(需 DB:A2/A3 重查)─────────────────────────────

@pytest.mark.asyncio
async def test_oidc_token_through_get_current_user(oidc_env, rsa_keys):
    assert await db_module._ensure_conn()
    private_pem, _ = rsa_keys
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, role) VALUES (%s::uuid, %s, %s, 'admin')",
        (uid, TID, f"oidc-{uid[:8]}@example.com"),
    )
    try:
        user = await get_current_user(
            _request(), "Bearer " + _casdoor_token(private_pem, user_id=uid))
        assert user.user_id == uid and user.role == "admin" and user.tenant_id == TID
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_oidc_disabled_account_403(oidc_env, rsa_keys):
    """A2 停權即時失效對 OIDC token 同樣生效(D3:下游零改動的證明)。"""
    assert await db_module._ensure_conn()
    private_pem, _ = rsa_keys
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, role, is_active) "
        "VALUES (%s::uuid, %s, %s, 'admin', FALSE)",
        (uid, TID, f"oidc-off-{uid[:8]}@example.com"),
    )
    try:
        with pytest.raises(ApiError) as e:
            await get_current_user(
                _request(), "Bearer " + _casdoor_token(private_pem, user_id=uid))
        assert e.value.status_code == 403 and e.value.error_code == "ACCOUNT_DISABLED"
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── cookie fallback(ACT-01 地基)─────────────────────────────────────────────

def test_extract_bearer_cookie_fallback():
    assert _extract_bearer(None, _request(cookie="tok-from-cookie")) == "tok-from-cookie"
    # header 優先於 cookie
    assert _extract_bearer("Bearer tok-hdr", _request(cookie="tok-cookie")) == "tok-hdr"
    with pytest.raises(ApiError):
        _extract_bearer(None, _request())


@pytest.mark.asyncio
async def test_legacy_hs256_token_still_works(oidc_env):
    """雙驗不影響自簽 token(既有體系迴歸)。"""
    assert await db_module._ensure_conn()
    from core.auth import create_token

    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, role) VALUES (%s::uuid, %s, %s, 'admin')",
        (uid, TID, f"legacy-{uid[:8]}@example.com"),
    )
    try:
        token, _, _ = create_token(user_id=uid, role="admin", tenant_id=TID,
                                   token_type="access")
        user = await get_current_user(_request(), "Bearer " + token)
        assert user.user_id == uid
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))
