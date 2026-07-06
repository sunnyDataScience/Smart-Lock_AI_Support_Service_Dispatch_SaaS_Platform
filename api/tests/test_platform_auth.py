"""CR-0114:platform console 登入/登出/me 與品牌⇄平台隔離。

單庫 fallback 模式(PLATFORM_POSTGRES_URI 未設,pytest 現況):
require_platform_conn() 回主連線 → 平台管理員列直接 seed 進 dev DB users 表,
測完清除。真雙庫行為由 compose 實測驗證(R1 Playwright)。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.auth import hash_password

pytestmark = pytest.mark.component

LOGIN = "/api/v1/platform/auth/login"
ME = "/api/v1/platform/me"
LOGOUT = "/api/v1/platform/auth/logout"
REFRESH = "/api/v1/platform/auth/refresh"

PASSWORD = "platform-test-pw-123"


async def _seed_platform_admin(email: str) -> str:
    """直接 INSERT 一個 platform_admin(fallback 模式與品牌 users 同表)。回 user_id。"""
    assert await db_module._ensure_conn()
    user_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'platform_admin', TRUE)",
        (
            user_id,
            "00000000-0000-0000-0000-000000000001",
            "測試平台管理員",
            email,
            hash_password(PASSWORD),
        ),
    )
    return user_id


async def _cleanup_user(user_id: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM revoked_jti WHERE user_id = %s::uuid", (user_id,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest.mark.asyncio
async def test_platform_login_me_logout_roundtrip(client):
    """登入 → me → 登出 → token 撤銷(me 401)。"""
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    user_id = await _seed_platform_admin(email)
    try:
        res = await client.post(LOGIN, json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        token = data["access_token"]
        assert data["refresh_token"]

        res = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["email"] == email
        assert res.json()["data"]["role"] == "platform_admin"

        res = await client.post(
            LOGOUT,
            json={"refresh_token": data["refresh_token"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 204, res.text

        res = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401, "登出後 access token 應已撤銷"
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_platform_login_wrong_password_401(client):
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    user_id = await _seed_platform_admin(email)
    try:
        res = await client.post(LOGIN, json={"email": email, "password": "wrong-password-1"})
        assert res.status_code == 401, res.text
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_platform_login_rejects_brand_admin_account(client):
    """品牌 admin 帳號(seed test@lock-ai.com)不能登平台 console(角色限定)。"""
    res = await client.post(
        LOGIN, json={"email": "test@lock-ai.com", "password": "changeme123"}
    )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_brand_token_cannot_access_platform_me(client, admin_token):
    """品牌 admin token 打 /platform/me → 403(platform_admin 限定)。"""
    res = await client.get(ME, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_platform_token_cannot_access_brand_endpoints(client):
    """平台 token 打品牌端點 → 403(不在品牌角色集 / tenant 不符)。"""
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    user_id = await _seed_platform_admin(email)
    try:
        res = await client.post(LOGIN, json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        token = res.json()["data"]["access_token"]

        res = await client.get(
            "/tenants/00000000-0000-0000-0000-000000000001/vendors",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert res.status_code == 403, res.text
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_platform_refresh_rotates_and_revokes_old(client):
    """refresh 換發成功且舊 refresh jti 被撤銷(rotate)。"""
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    user_id = await _seed_platform_admin(email)
    try:
        res = await client.post(LOGIN, json={"email": email, "password": PASSWORD})
        old_refresh = res.json()["data"]["refresh_token"]

        res = await client.post(REFRESH, json={"refresh_token": old_refresh})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["access_token"]

        res = await client.post(REFRESH, json={"refresh_token": old_refresh})
        assert res.status_code == 401, "旋轉後舊 refresh 應已撤銷"
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_platform_refresh_rejects_brand_refresh_token(client):
    """品牌帳號的 refresh token 不能換平台 token(role 檢查)。"""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@lock-ai.com", "password": "changeme123"},
    )
    assert res.status_code == 200, res.text
    brand_refresh = res.json()["data"]["refresh_token"]

    res = await client.post(REFRESH, json={"refresh_token": brand_refresh})
    assert res.status_code == 401, res.text
