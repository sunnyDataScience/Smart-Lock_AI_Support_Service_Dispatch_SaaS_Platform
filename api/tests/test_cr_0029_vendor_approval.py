"""CR-0029 收尾 — 廠商核准 service 測試（component，真 DB）。

- list_vendors(status=pending_approval) 列出新註冊廠商
- approve_vendor → status active + approved_by 設定
- 重複 approve → 409（非 pending）
- reject_vendor → status rejected + rejection_reason
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import auth_service, vendor_service
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _vendor_req(email: str) -> dict:
    return {
        "vendor_type": "locksmith", "name": "測試鎖店", "company_name": "測試鎖店行",
        "phone": "0912345678", "email": email, "password": "vendorpass123",
        "address": "新北市板橋區文化路1號",
    }


async def _cleanup(email: str) -> None:
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


@pytest.mark.asyncio
async def test_list_pending_then_approve(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        reg = await auth_service.register_vendor(_vendor_req(email))
        vid = reg["data"]["id"]
        # pending 列表含此廠商
        listed = await vendor_service.list_vendors(
            tenant_id=DEFAULT_TENANT_ID, status="pending_approval")
        assert any(v["id"] == vid for v in listed["items"])
        # approve → active + approved_by
        res = await vendor_service.approve_vendor(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=vid, approver_id=ADMIN_USER_ID)
        assert res["status"] == "active"
        assert res["approved_by"] == ADMIN_USER_ID
        # 重複 approve → 409（已非 pending）
        with pytest.raises(ApiError) as ei:
            await vendor_service.approve_vendor(
                tenant_id=DEFAULT_TENANT_ID, vendor_id=vid, approver_id=ADMIN_USER_ID)
        assert ei.value.status_code == 409
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_reject_vendor(client):
    assert await db_module._ensure_conn()
    email = f"vendor-{uuid.uuid4().hex[:8]}@example.com"
    try:
        reg = await auth_service.register_vendor(_vendor_req(email))
        vid = reg["data"]["id"]
        res = await vendor_service.reject_vendor(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=vid,
            approver_id=ADMIN_USER_ID, reason="資料不全")
        assert res["status"] == "rejected"
        assert res["rejection_reason"] == "資料不全"
    finally:
        await _cleanup(email)
