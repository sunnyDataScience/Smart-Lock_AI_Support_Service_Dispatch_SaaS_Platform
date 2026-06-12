"""管理員代為重設密碼（A4，會議 2026-06-10 Action #7）整合測試。

機制：admin/keeper 在後台重設指定使用者密碼為隨機臨時密碼,回傳明文供轉達;
不需 email 基礎設施（業主裁決：管理員代為重設）。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component

RESET_PATH = "/api/v1/auth/admin-reset-password"
# dispatcher 種子帳號（對齊 SQL/seeds/dispatcher_user.sql / conftest DISPATCHER_USER_ID）
TARGET_EMAIL = "dispatcher@example.com"


@pytest.mark.asyncio
async def test_admin_reset_returns_temp_password_and_new_password_works(
    client, admin_headers
):
    """admin 重設 → 回傳臨時密碼,且用該臨時密碼可通過驗證。"""
    res = await client.post(
        RESET_PATH, headers=admin_headers, json={"email": TARGET_EMAIL}
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    temp = data["temp_password"]
    assert isinstance(temp, str) and len(temp) >= 8
    assert data["email"] == TARGET_EMAIL

    # 用臨時密碼直接驗證（dispatcher 角色不在 /auth/login 的 allowed_roles,
    # 故走 service 層 login 驗證 hash 已更新）
    from services import auth_service

    login = await auth_service.login(
        email=TARGET_EMAIL, password=temp, allowed_roles=["dispatcher"]
    )
    assert login["data"]["access_token"]


@pytest.mark.asyncio
async def test_non_admin_cannot_reset(client, technician_headers):
    """非 admin 角色（technician）→ 403。"""
    res = await client.post(
        RESET_PATH, headers=technician_headers, json={"email": TARGET_EMAIL}
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_unknown_email_returns_404(client, admin_headers):
    """不存在的 email → 404 USER_NOT_FOUND。"""
    res = await client.post(
        RESET_PATH,
        headers=admin_headers,
        json={"email": "nobody-xyz@example.com"},
    )
    assert res.status_code == 404, res.text
