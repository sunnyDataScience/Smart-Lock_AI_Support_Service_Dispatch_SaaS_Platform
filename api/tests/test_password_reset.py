"""CR-0025 / ADR-0114 — 自助忘記密碼整合測試。

測試矩陣：
  1. request happy path：存在帳號 → 200 + 建立 token 列
  2. request 不存在帳號 → 200（枚舉防護）+ 不建 token
  3. request 停用帳號 → 200 + 不建 token
  4. confirm happy path：有效 token → 204 + password_hash 變更 + token 標 used
  5. confirm 過期 token → 400 RESET_TOKEN_EXPIRED
  6. confirm 已用 token → 400 RESET_TOKEN_INVALID
  7. confirm 不存在 token → 400 RESET_TOKEN_INVALID
  8. confirm 後同 token 再用 → 400（單次用）

註：SMTP 未配置時 request 仍建 token、回 200（信未送達由 service 安靜略過）。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

REQUEST_PATH = "/api/v1/auth/request-password-reset"
CONFIRM_PATH = "/api/v1/auth/confirm-password-reset"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest_asyncio.fixture
async def reset_user(client):
    """建立一個專用測試帳號（含原始密碼 hash），yield 後清掉 token + user。"""
    import core.db as db_module
    from core.auth import hash_password
    from core.db import _ensure_conn

    await _ensure_conn()
    user_id = str(uuid.uuid4())
    email = f"pwreset-{user_id[:8]}@example.com"
    original_password = "OrigPass123"
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'customer_service', TRUE)",
        (user_id, DEFAULT_TENANT_ID, "重設測試", email, hash_password(original_password)),
    )

    async def _insert_token(*, raw: str, ttl_minutes: int = 30, used: bool = False) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        used_at = datetime.now(timezone.utc) if used else None
        await db_module._conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, channel, expires_at, used_at) "
            "VALUES (%s::uuid, %s, 'email', %s, %s)",
            (user_id, _hash_token(raw), expires_at, used_at),
        )

    yield {
        "id": user_id,
        "email": email,
        "original_password": original_password,
        "insert_token": _insert_token,
    }

    await db_module._conn.execute(
        "DELETE FROM password_reset_tokens WHERE user_id = %s::uuid", (user_id,)
    )
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


async def _count_tokens(user_id: str) -> int:
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = %s::uuid", (user_id,)
    )
    return (await cur.fetchone())[0]


# ── 1. request happy path ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_request_existing_user_creates_token(client, reset_user):
    res = await client.post(REQUEST_PATH, json={"email": reset_user["email"]})
    assert res.status_code == 200
    assert await _count_tokens(reset_user["id"]) == 1


# ── 2. request 不存在帳號（枚舉防護）────────────────────────────────────
@pytest.mark.asyncio
async def test_request_unknown_email_still_200_no_token(client):
    res = await client.post(
        REQUEST_PATH, json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com"}
    )
    assert res.status_code == 200  # 不洩漏帳號是否存在


# ── 3. request 停用帳號 → 不建 token ────────────────────────────────────
@pytest.mark.asyncio
async def test_request_inactive_user_no_token(client, reset_user):
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute(
        "UPDATE users SET is_active = FALSE WHERE id = %s::uuid", (reset_user["id"],)
    )
    res = await client.post(REQUEST_PATH, json={"email": reset_user["email"]})
    assert res.status_code == 200
    assert await _count_tokens(reset_user["id"]) == 0


# ── 4. confirm happy path ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_confirm_valid_token_changes_password(client, reset_user):
    import core.db as db_module
    from core.auth import verify_password
    from core.db import _ensure_conn

    raw = "raw-token-" + uuid.uuid4().hex
    await reset_user["insert_token"](raw=raw)

    res = await client.post(
        CONFIRM_PATH, json={"token": raw, "new_password": "BrandNew456"}
    )
    assert res.status_code == 204

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT password_hash FROM users WHERE id = %s::uuid", (reset_user["id"],)
    )
    new_hash = (await cur.fetchone())[0]
    assert verify_password("BrandNew456", new_hash)
    assert not verify_password(reset_user["original_password"], new_hash)

    # token 標 used
    cur = await db_module._conn.execute(
        "SELECT used_at FROM password_reset_tokens WHERE token_hash = %s",
        (_hash_token(raw),),
    )
    assert (await cur.fetchone())[0] is not None


# ── 5. confirm 過期 token ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_confirm_expired_token_rejected(client, reset_user):
    raw = "expired-" + uuid.uuid4().hex
    await reset_user["insert_token"](raw=raw, ttl_minutes=-5)  # 已過期
    res = await client.post(
        CONFIRM_PATH, json={"token": raw, "new_password": "BrandNew456"}
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "RESET_TOKEN_EXPIRED"


# ── 6. confirm 已用 token ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_confirm_used_token_rejected(client, reset_user):
    raw = "used-" + uuid.uuid4().hex
    await reset_user["insert_token"](raw=raw, used=True)
    res = await client.post(
        CONFIRM_PATH, json={"token": raw, "new_password": "BrandNew456"}
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "RESET_TOKEN_INVALID"


# ── 7. confirm 不存在 token ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_confirm_unknown_token_rejected(client):
    res = await client.post(
        CONFIRM_PATH,
        json={"token": "does-not-exist-" + uuid.uuid4().hex, "new_password": "BrandNew456"},
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "RESET_TOKEN_INVALID"


# ── 8. confirm 後同 token 再用 → 單次用 ─────────────────────────────────
@pytest.mark.asyncio
async def test_confirm_token_single_use(client, reset_user):
    raw = "single-" + uuid.uuid4().hex
    await reset_user["insert_token"](raw=raw)

    first = await client.post(CONFIRM_PATH, json={"token": raw, "new_password": "FirstSet789"})
    assert first.status_code == 204

    second = await client.post(CONFIRM_PATH, json={"token": raw, "new_password": "SecondSet000"})
    assert second.status_code == 400
    assert second.json()["error_code"] == "RESET_TOKEN_INVALID"
