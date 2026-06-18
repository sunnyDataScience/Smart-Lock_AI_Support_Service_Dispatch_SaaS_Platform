"""CR-0029 廠商/師傅雙路註冊測試（component，真 DB）。

驗證：
- register_vendor → users(role=vendor, tenant_type=requestor) + vendors 兩列、status pending_approval
- email 全域去重 → 409
- vendor_type 非法 → 422
- vendor 註冊後可用 vendors/login 登入；但不能登後台（allowed_roles 隔離）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import auth_service

pytestmark = pytest.mark.component


def _vendor_req(email: str) -> dict:
    return {
        "vendor_type": "brand",
        "name": "測試品牌商",
        "company_name": "測試鎖業股份有限公司",
        "phone": "0912345678",
        "email": email,
        "password": "vendorpass123",
        "address": "新北市板橋區文化路1號",
    }


async def _cleanup(email: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM users WHERE email = %s", (email,)
    )  # vendors 透過 ON DELETE CASCADE 一併刪


@pytest.mark.asyncio
async def test_register_vendor_creates_user_and_vendor(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await auth_service.register_vendor(_vendor_req(email))
        assert res["data"]["status"] == "pending_approval"
        assert res["data"]["vendor_type"] == "brand"
        # users：role=vendor / tenant_type=requestor
        cur = await db_module._conn.execute(
            "SELECT role, tenant_type FROM users WHERE email = %s", (email,)
        )
        row = await cur.fetchone()
        assert row == ("vendor", "requestor")
        # vendors 列存在
        vcur = await db_module._conn.execute(
            "SELECT status, vendor_type FROM vendors WHERE email = %s", (email,)
        )
        vrow = await vcur.fetchone()
        assert vrow == ("pending_approval", "brand")
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_register_vendor_email_dup_409(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.register_vendor(_vendor_req(email))
        with pytest.raises(ApiError) as ei:
            await auth_service.register_vendor(_vendor_req(email))
        assert ei.value.status_code == 409
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_register_vendor_invalid_type_422(client):
    assert await db_module._ensure_conn()
    req = _vendor_req(f"vendor-{uuid.uuid4().hex[:8]}@example.com")
    req["vendor_type"] = "bogus"
    with pytest.raises(ApiError) as ei:
        await auth_service.register_vendor(req)
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_vendor_can_login_but_not_admin_web(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.register_vendor(_vendor_req(email))
        # vendors/login（allowed_roles=['vendor']）成功
        ok = await auth_service.login(
            email=email, password="vendorpass123", allowed_roles=["vendor"])
        assert ok.get("access_token") or ok.get("data")
        # 不能登後台（allowed_roles 不含 vendor）→ 應拒
        with pytest.raises(ApiError):
            await auth_service.login(
                email=email, password="vendorpass123",
                allowed_roles=["admin", "operations_manager", "dispatcher", "customer_service"])
    finally:
        await _cleanup(email)
