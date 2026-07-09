"""CR-0094 後台員工帳號建立（解「5 角色只有 admin」）。

- create_staff_user：合法角色建 users 列（即時 active）、非法角色 422、短密碼 422、
  同 email+role 重複 409
- 端點 role 隔離：technician → 403、admin → 201
- list_staff_users 含新建帳號
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import auth_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _req(email: str, role: str = "operations_manager") -> dict:
    return {"name": "測試員工", "email": email, "password": "staffpass123", "role": role}


async def _cleanup(email: str) -> None:
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


@pytest.mark.asyncio
async def test_create_staff_ok(client):
    assert await db_module._ensure_conn()
    email = f"staff-{uuid.uuid4().hex[:8]}@example.com"
    try:
        out = await auth_service.create_staff_user(_req(email, "reviewer"), tenant_id=DEFAULT_TENANT_ID)
        assert out["data"]["role"] == "reviewer"
        assert out["data"]["is_active"] is True
        cur = await db_module._conn.execute(
            "SELECT role, tenant_type, is_active FROM users WHERE email = %s", (email,))
        row = await cur.fetchone()
        assert row[0] == "reviewer" and row[1] == "platform" and row[2] is True
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_create_staff_invalid_role_422(client):
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await auth_service.create_staff_user(_req("x@example.com", "technician"), tenant_id=DEFAULT_TENANT_ID)
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_create_staff_reserved_dispatcher_422(client):
    """dispatcher 為保留角色（13_Security §3.1，SA-06）——不可再開通新帳號。"""
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await auth_service.create_staff_user(
            _req("reserved-dispatcher@example.com", "dispatcher"), tenant_id=DEFAULT_TENANT_ID)
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_create_staff_short_password_422(client):
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await auth_service.create_staff_user(
            {"name": "x", "email": "y@example.com", "password": "short", "role": "customer_service"},
            tenant_id=DEFAULT_TENANT_ID)
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_create_staff_duplicate_same_role_409(client):
    assert await db_module._ensure_conn()
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.create_staff_user(_req(email, "customer_service"), tenant_id=DEFAULT_TENANT_ID)
        with pytest.raises(ApiError) as ei:
            await auth_service.create_staff_user(_req(email, "customer_service"), tenant_id=DEFAULT_TENANT_ID)
        assert ei.value.status_code == 409
    finally:
        await _cleanup(email)


async def test_endpoint_technician_forbidden(client, technician_headers):
    resp = await client.post(
        "/api/v1/staff", json=_req("z@example.com"), headers=technician_headers)
    assert resp.status_code == 403, resp.text


async def test_reviewer_can_access_refunds(client):
    # CR-0094 對齊 _MATRIX：reviewer 可寫退款 → 不應被 role_required 403
    # （可能因缺 SoD header 422，但不是 403=角色被擋）
    from tests.conftest import _make_token

    tok = _make_token(user_id=str(uuid.uuid4()), role="reviewer")
    h = {"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID}
    resp = await client.post(f"/tenants/{DEFAULT_TENANT_ID}/refunds", json={}, headers=h)
    assert resp.status_code != 403, f"reviewer 應可存取退款，得 403: {resp.text[:200]}"


async def test_endpoint_admin_creates_and_lists(client, admin_headers):
    assert await db_module._ensure_conn()
    email = f"ep-{uuid.uuid4().hex[:8]}@example.com"
    try:
        resp = await client.post(
            "/api/v1/staff", json=_req(email, "customer_service"), headers=admin_headers)
        assert resp.status_code == 201, resp.text
        lst = await client.get("/api/v1/staff", headers=admin_headers)
        assert lst.status_code == 200
        emails = [s["email"] for s in lst.json()["items"]]
        assert email in emails
    finally:
        await _cleanup(email)
