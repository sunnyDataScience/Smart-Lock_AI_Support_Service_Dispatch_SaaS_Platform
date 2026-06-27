"""Phase I 帳號安全 A1/A2/A3 元件測試。

  A1 登入防爆破：
    A1-1 連續失敗達上限 → 帳號鎖定（即使密碼正確也回 429 LOGIN_LOCKED）
    A1-2 上限內失敗後成功登入 → 計數歸零（failed_login_attempts=0）
  A2 停權 token 即時失效：
    A2-1 既存帳號 is_active=FALSE → 既簽 token 打受保護端點 403 ACCOUNT_DISABLED
    A2-2 控制組：active 帳號 token → 204（不誤殺）
  A3 改密碼撤既有 session：
    A3-1 token iat 早於 password_changed_at → 401 TOKEN_STALE
    A3-2 控制組：password_changed_at 早於 token iat → 通過
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID


async def _create_user(*, role: str = "admin", password: str = "Sup3rSecret!") -> tuple[str, str, str]:
    """直接 INSERT 一個已知密碼的測試帳號，回 (user_id, email, password)。"""
    import core.db as db_module
    from core.auth import hash_password

    await db_module._ensure_conn()
    user_id = str(uuid.uuid4())
    email = f"sec-{user_id[:8]}@example.com"
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, tenant_type, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, 'platform', %s, %s, %s, %s, TRUE)",
        (user_id, DEFAULT_TENANT_ID, f"sec-{user_id[:8]}", email, hash_password(password), role),
    )
    return user_id, email, password


async def _cleanup(user_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


def _access_token(user_id: str, role: str = "admin") -> str:
    from core.auth import create_token

    tok, _jti, _exp = create_token(
        user_id=user_id, role=role, tenant_id=DEFAULT_TENANT_ID, token_type="access"
    )
    return tok


# ----------------------------- A1 -----------------------------


@pytest.mark.asyncio
@pytest.mark.component
async def test_a1_lockout_after_max_attempts(client):
    """A1-1：連續 5 次密碼錯誤 → 鎖定，正確密碼也回 429。"""
    user_id, email, password = await _create_user()
    try:
        for _ in range(5):
            r = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPass99"})
            assert r.status_code == 401, r.text
        # 鎖定後，即使密碼正確也擋
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 429, r.text
        assert r.json()["error_code"] == "LOGIN_LOCKED"
    finally:
        await _cleanup(user_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_a1_success_resets_failures(client):
    """A1-2：上限內失敗後成功登入 → 計數歸零。"""
    import core.db as db_module

    user_id, email, password = await _create_user()
    try:
        for _ in range(2):
            r = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPass99"})
            assert r.status_code == 401, r.text
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        cur = await db_module._conn.execute(
            "SELECT failed_login_attempts, locked_until FROM users WHERE id = %s::uuid", (user_id,)
        )
        row = await cur.fetchone()
        assert row[0] == 0 and row[1] is None
    finally:
        await _cleanup(user_id)


# ----------------------------- A2 -----------------------------


@pytest.mark.asyncio
@pytest.mark.component
async def test_a2_suspended_user_token_rejected(client):
    """A2-1：既簽 token 的帳號被停權（is_active=FALSE）→ 受保護端點 403。"""
    import core.db as db_module

    user_id, _email, _pw = await _create_user()
    token = _access_token(user_id)
    try:
        # 控制組：active → logout 204
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204, r.text

        # 停權後，重簽一顆新 token（舊的已因 logout 撤銷）→ 應被擋
        await db_module._conn.execute(
            "UPDATE users SET is_active = FALSE WHERE id = %s::uuid", (user_id,)
        )
        token2 = _access_token(user_id)
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token2}"})
        assert r.status_code == 403, r.text
        assert r.json()["error_code"] == "ACCOUNT_DISABLED"
    finally:
        await _cleanup(user_id)


# ----------------------------- A3 -----------------------------


@pytest.mark.asyncio
@pytest.mark.component
async def test_a3_token_before_password_change_rejected(client):
    """A3-1：token iat 早於 password_changed_at → 401 TOKEN_STALE。"""
    import core.db as db_module

    user_id, _email, _pw = await _create_user()
    token = _access_token(user_id)
    try:
        # 把 password_changed_at 設在 token iat 之後（+5 秒）→ 既有 token 失效
        await db_module._conn.execute(
            "UPDATE users SET password_changed_at = NOW() + interval '5 seconds' WHERE id = %s::uuid",
            (user_id,),
        )
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, r.text
        assert r.json()["error_code"] == "TOKEN_STALE"
    finally:
        await _cleanup(user_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_a3_token_after_password_change_ok(client):
    """A3-2：password_changed_at 早於 token iat（過去）→ 通過（不誤殺新 token）。"""
    import core.db as db_module

    user_id, _email, _pw = await _create_user()
    try:
        await db_module._conn.execute(
            "UPDATE users SET password_changed_at = NOW() - interval '1 hour' WHERE id = %s::uuid",
            (user_id,),
        )
        token = _access_token(user_id)  # iat = now，晚於 password_changed_at
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204, r.text
    finally:
        await _cleanup(user_id)
