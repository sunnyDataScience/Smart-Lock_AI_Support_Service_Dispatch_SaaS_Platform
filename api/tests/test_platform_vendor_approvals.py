"""CR-0114 收尾：廠商審核搬到 platform console。

`vendors`（發案方登入帳號）的註冊審核自品牌後台移到平台方。本檔驗證
platform_vendors.py 端點：
  - GET  /platform/vendors?status=
  - POST /platform/vendors/{id}:approve
  - POST /platform/vendors/{id}:reject

全部 gate = require_platform_admin：品牌 admin token 應 403、無 token 應 401。
品牌端 approve/reject 寫端點已移除（405）；GET 唯讀保留。
vendors 住主品牌庫（單庫 fallback = 主連線）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import auth_service

pytestmark = pytest.mark.component

PLATFORM_VENDORS = "/api/v1/platform/vendors"
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _vendor_req(email: str) -> dict:
    return {
        "vendor_type": "locksmith", "name": "平台廠商測試", "company_name": "平台廠商測試行",
        "phone": "0912345678", "email": email, "password": "vendorpass123",
        "address": "新北市板橋區文化路1號",
    }


async def _register(email: str) -> str:
    reg = await auth_service.register_vendor(_vendor_req(email))
    return reg["data"]["id"]


async def _cleanup(email: str) -> None:
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
async def test_approve_requires_platform_admin(client, admin_headers):
    fake = str(uuid.uuid4())
    res = await client.post(f"{PLATFORM_VENDORS}/{fake}:approve")
    assert res.status_code == 401
    res = await client.post(f"{PLATFORM_VENDORS}/{fake}:approve", headers=admin_headers)
    assert res.status_code == 403


# ── 核准 / 拒絕流程 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pending_then_approve(client, platform_admin_headers):
    assert await db_module._ensure_conn()
    email = f"plat-vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        vid = await _register(email)
        # pending 清單含此廠商
        lst = await client.get(f"{PLATFORM_VENDORS}?status=pending_approval", headers=platform_admin_headers)
        assert lst.status_code == 200, lst.text
        assert any(v["id"] == vid for v in lst.json()["items"])
        # 核准 → active
        res = await client.post(f"{PLATFORM_VENDORS}/{vid}:approve", headers=platform_admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "active"
        # 重複核准 → 409（已非 pending）
        dup = await client.post(f"{PLATFORM_VENDORS}/{vid}:approve", headers=platform_admin_headers)
        assert dup.status_code == 409, dup.text
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_reject_vendor(client, platform_admin_headers):
    assert await db_module._ensure_conn()
    email = f"plat-vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        vid = await _register(email)
        res = await client.post(
            f"{PLATFORM_VENDORS}/{vid}:reject",
            headers=platform_admin_headers, json={"reason": "資料不全"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "rejected"
        assert res.json()["data"]["rejection_reason"] == "資料不全"
    finally:
        await _cleanup(email)


# ── 品牌端 approve/reject 已移除 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_brand_approve_reject_removed(client, admin_headers):
    """CR-0114 收尾：品牌端廠商核准/拒絕寫端點整條移除 → 404（冒號動詞路徑不存在）。
    GET 唯讀清單保留。"""
    fake = str(uuid.uuid4())
    approve = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/vendors/{fake}:approve", headers=admin_headers)
    assert approve.status_code == 404, approve.text
    reject = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/vendors/{fake}:reject",
        headers=admin_headers, json={"reason": "x"})
    assert reject.status_code == 404, reject.text
    # GET 唯讀仍在
    lst = await client.get(f"/tenants/{DEFAULT_TENANT_ID}/vendors", headers=admin_headers)
    assert lst.status_code == 200, lst.text
