"""CR-0090 技師與廠商共用同一 email（component，真 DB）。

驗證 email 唯一性不變式由「全域唯一」放寬為「每角色唯一」：
- 同 email 可同時註冊為技師 + 廠商（兩列 users，role 各異）→ 皆成功
- 同角色內重複 email 仍 409（技師×技師、廠商×廠商）
- 兩帳號各自走 /technicians/login、/vendors/login 登入（role 過濾分辨）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from tests.conftest import seed_required_kyc_docs  # CR-0195 核准需文件齊全
from core.errors import ApiError
from services import auth_service

pytestmark = pytest.mark.component


def _tech_req(email: str) -> dict:
    return {
        "name": "共用技師",
        "phone": "0912345678",
        "email": email,
        "password": "techpass123",
    }


def _vendor_req(email: str) -> dict:
    return {
        "vendor_type": "brand",
        "name": "共用廠商聯絡人",
        "company_name": "共用測試公司",
        "tax_id": "12345678",
        "phone": "0922000111",
        "email": email,
        "password": "vendorpass123",
        "address": "台北市",
    }


async def _cleanup(email: str) -> None:
    # 一個 email 可能對應兩列 users（tech + vendor）；CASCADE 一併刪 technicians/vendors
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


@pytest.mark.asyncio
async def test_same_email_technician_and_vendor_ok(client):
    assert await db_module._ensure_conn()
    email = f"both-{uuid.uuid4().hex[:8]}@example.com"
    try:
        tech = await auth_service.register_technician(_tech_req(email))
        vendor = await auth_service.register_vendor(_vendor_req(email))
        assert tech["data"]["status"] == "pending_approval"
        # UAT R2 W3-2：廠商改平台代建，建立即 active（無待審流）
        assert vendor["data"]["status"] == "active"
        # 兩列 users：role technician + vendor
        cur = await db_module._conn.execute(
            "SELECT role FROM users WHERE email = %s ORDER BY role", (email,)
        )
        roles = [r[0] for r in await cur.fetchall()]
        assert roles == ["technician", "vendor"]
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_duplicate_technician_email_still_409(client):
    assert await db_module._ensure_conn()
    email = f"dup-tech-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.register_technician(_tech_req(email))
        with pytest.raises(ApiError) as ei:
            await auth_service.register_technician(_tech_req(email))
        assert ei.value.status_code == 409
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_duplicate_vendor_email_still_409(client):
    assert await db_module._ensure_conn()
    email = f"dup-vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await auth_service.register_vendor(_vendor_req(email))
        with pytest.raises(ApiError) as ei:
            await auth_service.register_vendor(_vendor_req(email))
        assert ei.value.status_code == 409
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_both_accounts_login_by_role(client):
    assert await db_module._ensure_conn()
    email = f"login-{uuid.uuid4().hex[:8]}@example.com"
    try:
        tech = await auth_service.register_technician(_tech_req(email))
        await auth_service.register_vendor(_vendor_req(email))
        # 2026-07-02 登入狀態閘：技師註冊後 is_active=FALSE（待核准不可登入），
        # 本測試主題是「同 email 依角色分流」→ 先核准讓技師可登入。
        from services import technician_lifecycle_service

        # CR-0195：核准需 KYC 文件齊全；本測試主題是 email 角色分流，補齊即可
        await seed_required_kyc_docs(tech["data"]["id"])
        await technician_lifecycle_service.approve_onboarding(
            tenant_id="00000000-0000-0000-0000-000000000001",
            tech_id=tech["data"]["id"],
            actor_user_id=None,
        )
        # 技師端點以 techpass 登入技師帳號
        t = await auth_service.login(
            email=email, password="techpass123", allowed_roles=["technician"]
        )
        assert t.get("data") or t.get("access_token")
        # 廠商端點以 vendorpass 登入廠商帳號
        v = await auth_service.login(
            email=email, password="vendorpass123", allowed_roles=["vendor"]
        )
        assert v.get("data") or v.get("access_token")
    finally:
        await _cleanup(email)
