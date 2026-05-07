"""認證 / 權限 guard 整合測試。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_missing_authorization_returns_401(client):
    res = await client.get("/api/v1/work-orders")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    res = await client.get(
        "/api/v1/work-orders",
        headers={"Authorization": "Bearer not-a-jwt", "X-Tenant-ID": "00000000-0000-0000-0000-000000000001"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_list_work_orders(client, admin_headers):
    res = await client.get("/api/v1/work-orders", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_tenant_mismatch_returns_403(client, admin_token):
    # 故意傳錯 tenant 不對應的 X-Tenant-ID
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    }
    res = await client.get("/api/v1/work-orders", headers=headers)
    assert res.status_code == 403
