"""Customer CRUD component tests — POST / PUT / GET。

涵蓋：
  - createCustomer 成功
  - createCustomer 缺 display_name → 422
  - createCustomer 重複 line_user_id → 422
  - createCustomer 角色不足 → 403
  - updateCustomer 成功（PUT 整體取代）
  - updateCustomer not found → 404
  - updateCustomer 缺 display_name → 422
  - getCustomer 不存在 → 404
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.component


def _unique_phone() -> str:
    """Tests share a DB; use a distinct phone per case."""
    return f"09{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_create_customer_success(client, admin_headers):
    body = {
        "display_name": f"測試客戶_{uuid.uuid4().hex[:6]}",
        "phone": _unique_phone(),
        "address": "台北市信義區信義路五段 7 號",
    }
    res = await client.post(
        "/api/v1/customers", json=body, headers=admin_headers
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["display_name"] == body["display_name"]
    assert data["phone"] == body["phone"]
    assert data["total_orders"] == 0
    assert data["total_conversations"] == 0


@pytest.mark.asyncio
async def test_create_customer_missing_display_name_returns_422(
    client, admin_headers
):
    res = await client.post(
        "/api/v1/customers",
        json={"phone": _unique_phone()},
        headers=admin_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_duplicate_line_user_id_returns_422(
    client, admin_headers
):
    line_id = f"U{uuid.uuid4().hex}"
    body = {
        "display_name": "客戶 A",
        "line_user_id": line_id,
    }
    r1 = await client.post(
        "/api/v1/customers", json=body, headers=admin_headers
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/customers",
        json={**body, "display_name": "客戶 B"},
        headers=admin_headers,
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_forbidden_for_non_admin(client):
    """Reviewer 角色不能寫客戶；應拿到 403。"""
    from tests.conftest import DEFAULT_TENANT_ID, _make_token

    reviewer_token = _make_token(
        user_id="22222222-2222-2222-2222-222222222222", role="reviewer"
    )
    headers = {
        "Authorization": f"Bearer {reviewer_token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }
    res = await client.post(
        "/api/v1/customers",
        json={"display_name": "should fail"},
        headers=headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_customer_success(client, admin_headers):
    # 先建立
    create_res = await client.post(
        "/api/v1/customers",
        json={
            "display_name": "原始名稱",
            "phone": _unique_phone(),
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    customer_id = create_res.json()["data"]["id"]

    # 更新
    update_res = await client.put(
        f"/api/v1/customers/{customer_id}",
        json={
            "display_name": "更新後名稱",
            "phone": _unique_phone(),
            "address": "新北市板橋區",
        },
        headers=admin_headers,
    )
    assert update_res.status_code == 200, update_res.text
    data = update_res.json()["data"]
    assert data["display_name"] == "更新後名稱"
    assert data["address"] == "新北市板橋區"


@pytest.mark.asyncio
async def test_update_customer_not_found_returns_404(client, admin_headers):
    fake_id = "00000000-0000-0000-0000-000000000fff"
    res = await client.put(
        f"/api/v1/customers/{fake_id}",
        json={"display_name": "ghost"},
        headers=admin_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_customer_missing_display_name_returns_422(
    client, admin_headers
):
    create_res = await client.post(
        "/api/v1/customers",
        json={"display_name": "初始", "phone": _unique_phone()},
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    customer_id = create_res.json()["data"]["id"]

    res = await client.put(
        f"/api/v1/customers/{customer_id}",
        json={"phone": _unique_phone()},  # missing display_name
        headers=admin_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_customer_not_found_returns_404(client, admin_headers):
    fake_id = "00000000-0000-0000-0000-000000000eee"
    res = await client.get(
        f"/api/v1/customers/{fake_id}", headers=admin_headers
    )
    assert res.status_code == 404
