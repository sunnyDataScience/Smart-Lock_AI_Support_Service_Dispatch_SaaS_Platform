"""UAT R2 W3-2 業主裁決（2026-07-18）：廠商自助註冊退場 → 平台代建。

本檔驗證 platform_vendors.py 端點：
  - GET  /platform/vendors?status=          清單保留
  - POST /platform/vendors                  代建（建立即 active）

以及退場面：
  - 公開 POST /vendors/register 已移除 → 404
  - POST /platform/vendors/{id}:approve / :reject 已移除 → 404

全部寫端點 gate = require_platform_admin：品牌 admin token 403、無 token 401。
vendors 住主品牌庫（單庫 fallback = 主連線）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

PLATFORM_VENDORS = "/api/v1/platform/vendors"
VENDOR_LOGIN = "/api/v1/vendors/login"


def _create_body(email: str) -> dict:
    return {
        "name": "平台代建測試", "company_name": "平台代建測試行",
        "tax_id": "12345678", "phone": "0912345678",
        "email": email, "password": "vendorpass123",
    }


async def _cleanup(email: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


# ── RBAC ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_requires_platform_admin(client, admin_headers, platform_admin_headers):
    res = await client.get(PLATFORM_VENDORS)
    assert res.status_code == 401, "無 token → 401"
    res = await client.get(PLATFORM_VENDORS, headers=admin_headers)
    assert res.status_code == 403, "品牌 admin 不可讀平台廠商清單"
    res = await client.get(PLATFORM_VENDORS, headers=platform_admin_headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_create_requires_platform_admin(client, admin_headers):
    body = _create_body("rbac-vendor@example.com")
    res = await client.post(PLATFORM_VENDORS, json=body)
    assert res.status_code == 401
    res = await client.post(PLATFORM_VENDORS, json=body, headers=admin_headers)
    assert res.status_code == 403


# ── 代建流程 ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_vendor_active_and_can_login(client, platform_admin_headers):
    """代建 201 → status 直接 active（不走待審）→ loginVendor 可登入。"""
    assert await db_module._ensure_conn()
    email = f"plat-create-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await client.post(
            PLATFORM_VENDORS, json=_create_body(email), headers=platform_admin_headers)
        assert res.status_code == 201, res.text
        data = res.json()["data"]
        assert data["status"] == "active"
        assert data["tax_id"] == "12345678"
        vid = data["id"]

        # DB：users(role=vendor) + vendors(status=active, approved_at 已記)
        cur = await db_module._conn.execute(
            "SELECT role, tenant_type, is_active FROM users WHERE email = %s", (email,))
        assert (await cur.fetchone()) == ("vendor", "requestor", True)
        cur = await db_module._conn.execute(
            "SELECT status, approved_at IS NOT NULL FROM vendors WHERE email = %s", (email,))
        assert (await cur.fetchone()) == ("active", True)

        # 平台清單可見（active 過濾）
        lst = await client.get(
            f"{PLATFORM_VENDORS}?status=active", headers=platform_admin_headers)
        assert lst.status_code == 200, lst.text
        assert any(v["id"] == vid for v in lst.json()["items"])

        # 代建後可直接登入
        login = await client.post(
            VENDOR_LOGIN, json={"email": email, "password": "vendorpass123"})
        assert login.status_code == 200, login.text
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_create_vendor_duplicate_email_409(client, platform_admin_headers):
    assert await db_module._ensure_conn()
    email = f"plat-dup-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await client.post(
            PLATFORM_VENDORS, json=_create_body(email), headers=platform_admin_headers)
        assert res.status_code == 201, res.text
        dup = await client.post(
            PLATFORM_VENDORS, json=_create_body(email), headers=platform_admin_headers)
        assert dup.status_code == 409, dup.text
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [("tax_id", "1234"), ("tax_id", "abcdefgh"), ("phone", "12345678"), ("email", "not-an-email")],
)
async def test_create_vendor_validation_422(client, platform_admin_headers, field, value):
    body = {**_create_body("v422@example.com"), field: value}
    res = await client.post(PLATFORM_VENDORS, json=body, headers=platform_admin_headers)
    assert res.status_code == 422, res.text


# ── 退場面：自助註冊與核准/拒絕端點皆移除 ────────────────────────────────────


@pytest.mark.asyncio
async def test_public_vendor_register_removed(client):
    """20260702 退場決議貫徹：公開自助註冊端點整條移除 → 404。"""
    res = await client.post(
        "/api/v1/vendors/register",
        json={**_create_body("removed@example.com"), "vendor_type": "brand"},
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_platform_approve_reject_removed(client, platform_admin_headers):
    """代建即 active → 平台核准/拒絕端點一併移除 → 404。"""
    fake = str(uuid.uuid4())
    res = await client.post(
        f"{PLATFORM_VENDORS}/{fake}:approve", headers=platform_admin_headers)
    assert res.status_code == 404, res.text
    res = await client.post(
        f"{PLATFORM_VENDORS}/{fake}:reject",
        headers=platform_admin_headers, json={"reason": "x"})
    assert res.status_code == 404, res.text
