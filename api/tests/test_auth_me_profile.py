"""自助個人資料端點 GET/PATCH /auth/me（settings 個人資料頁）。

驗證：
  1. GET /auth/me 回傳 display_name / email / phone / role
  2. PATCH 更新 display_name + phone（本人）
  3. 空白 display_name → 422
  4. 未認證 → 401
"""

import pytest


@pytest.mark.asyncio
async def test_get_my_profile(client, admin_headers):
    res = await client.get("/api/v1/auth/me", headers=admin_headers)
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert {"display_name", "email", "phone", "role"} <= set(data)
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_update_my_profile_roundtrip(client, admin_headers):
    orig = await client.get("/api/v1/auth/me", headers=admin_headers)
    if orig.status_code == 503:
        pytest.skip("DB not available")
    original = orig.json()["data"]

    res = await client.patch(
        "/api/v1/auth/me",
        headers=admin_headers,
        json={"display_name": "自助改名測試", "phone": "0912000111"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["display_name"] == "自助改名測試"
    assert data["phone"] == "0912000111"

    # 還原
    await client.patch(
        "/api/v1/auth/me",
        headers=admin_headers,
        json={
            "display_name": original["display_name"] or "系統管理員",
            "phone": original["phone"],
        },
    )


@pytest.mark.asyncio
async def test_update_my_profile_blank_name_422(client, admin_headers):
    res = await client.patch(
        "/api/v1/auth/me",
        headers=admin_headers,
        json={"display_name": "   "},
    )
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_get_my_profile_unauth_401(client):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403), res.text
