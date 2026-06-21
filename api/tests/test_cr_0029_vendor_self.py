"""CR-0029 廠商專區 — GET /vendors/me（廠商自身 profile）。

- vendor token → 200 + 自身 profile
- 查無對應 vendor → 404
- 非 vendor 角色（admin）→ 403（role_required("vendor")）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import auth_service
from tests.conftest import DEFAULT_TENANT_ID, _make_token

pytestmark = pytest.mark.component


def _vendor_req(email: str) -> dict:
    return {
        "vendor_type": "brand",
        "name": "廠商聯絡人",
        "company_name": "測試廠商公司",
        "tax_id": "12345678",
        "phone": "0922000111",
        "email": email,
        "password": "vendorpass123",
        "address": "台北市",
    }


async def _cleanup(email: str) -> None:
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


async def test_vendor_me_returns_self(client):
    assert await db_module._ensure_conn()
    email = f"vme-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.register_vendor(_vendor_req(email))
        cur = await db_module._conn.execute(
            "SELECT id FROM users WHERE email = %s AND role = 'vendor'", (email,))
        uid = str((await cur.fetchone())[0])
        tok = _make_token(user_id=uid, role="vendor")
        resp = await client.get(
            "/vendors/me",
            headers={"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["email"] == email
    finally:
        await _cleanup(email)


async def test_vendor_me_admin_forbidden(client, admin_headers):
    resp = await client.get("/vendors/me", headers=admin_headers)
    assert resp.status_code == 403, resp.text


async def test_vendor_me_no_profile_404(client):
    # vendor 角色 token 但無對應 vendors 列 → 404
    tok = _make_token(user_id=str(uuid.uuid4()), role="vendor")
    resp = await client.get(
        "/vendors/me",
        headers={"Authorization": f"Bearer {tok}", "X-Tenant-ID": DEFAULT_TENANT_ID},
    )
    assert resp.status_code == 404, resp.text
