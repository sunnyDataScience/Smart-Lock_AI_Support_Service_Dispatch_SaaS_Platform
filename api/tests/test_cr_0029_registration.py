"""CR-0029 → UAT R2 W3-2 收斂：廠商建立核心 service 測試（component，真 DB）。

公開自助註冊路徑已移除；register_vendor 改為平台代建復用核心
（initial_status 預設 'active'，建立即啟用）。驗證：
- register_vendor → users(role=vendor, tenant_type=requestor) + vendors 兩列、status active
- email 角色內去重 → 409
- vendor_type / initial_status 非法 → 422
- 代建後可用 vendors/login 登入；但不能登後台（allowed_roles 隔離）
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
async def test_register_vendor_creates_user_and_vendor_active(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await auth_service.register_vendor(_vendor_req(email))
        assert res["data"]["status"] == "active", "代建預設建立即啟用"
        assert res["data"]["vendor_type"] == "brand"
        # users：role=vendor / tenant_type=requestor
        cur = await db_module._conn.execute(
            "SELECT role, tenant_type FROM users WHERE email = %s", (email,)
        )
        row = await cur.fetchone()
        assert row == ("vendor", "requestor")
        # vendors 列存在且 active + approved_at 已記
        vcur = await db_module._conn.execute(
            "SELECT status, vendor_type, approved_at IS NOT NULL FROM vendors WHERE email = %s",
            (email,),
        )
        vrow = await vcur.fetchone()
        assert vrow == ("active", "brand", True)
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
async def test_register_vendor_invalid_initial_status_422(client):
    assert await db_module._ensure_conn()
    req = _vendor_req(f"vendor-{uuid.uuid4().hex[:8]}@example.com")
    with pytest.raises(ApiError) as ei:
        await auth_service.register_vendor(req, initial_status="rejected")
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
