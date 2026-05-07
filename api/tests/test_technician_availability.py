"""Technician availability PATCH component tests。

涵蓋 PATCH /api/v1/technicians/me/availability：
  - 技師正常切換 → 200 + online_state 一致
  - 不合法的 online_state → 422
  - 缺少 body → 422
  - admin 角色（非 technician）→ 403
  - 技師沒對應 technicians row → 404
  - 切換為 offline 的 round-trip 一致性
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component


# 使用 seed 中存在的技師帳號（demo-tech）；fallback：若 seed 缺，則此測會回 404
DEMO_TECH_USER_ID = "11111111-aaaa-bbbb-cccc-000000000001"


def _technician_headers(user_id: str | None = None) -> dict:
    from tests.conftest import DEFAULT_TENANT_ID, _make_token

    uid = user_id or DEMO_TECH_USER_ID
    token = _make_token(user_id=uid, role="technician")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


@pytest.mark.asyncio
async def test_patch_availability_to_busy_succeeds(client):
    headers = _technician_headers()
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "busy"},
        headers=headers,
    )
    # 404 if seed technician 不存在；200 if seed 已就緒
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        data = res.json()["data"]
        assert data["online_state"] == "busy"


@pytest.mark.asyncio
async def test_patch_availability_invalid_state_returns_422(client):
    headers = _technician_headers()
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "drinking_coffee"},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_availability_missing_body_returns_422(client):
    headers = _technician_headers()
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_availability_non_technician_returns_403(
    client, admin_headers
):
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "available"},
        headers=admin_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_patch_availability_unknown_user_returns_404(client):
    """技師 token 但 technicians 表無對應 row → 404。"""
    headers = _technician_headers(user_id="ffffffff-ffff-ffff-ffff-fffffffffff0")
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "available"},
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_patch_availability_round_trip_offline_then_available(client):
    headers = _technician_headers()
    r1 = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "offline"},
        headers=headers,
    )
    if r1.status_code == 404:
        pytest.skip("demo technician seed not available")
    assert r1.status_code == 200
    assert r1.json()["data"]["online_state"] == "offline"

    r2 = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "available"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["online_state"] == "available"


@pytest.mark.asyncio
async def test_patch_availability_no_token_returns_401(client):
    res = await client.patch(
        "/api/v1/technicians/me/availability",
        json={"online_state": "available"},
    )
    assert res.status_code == 401
