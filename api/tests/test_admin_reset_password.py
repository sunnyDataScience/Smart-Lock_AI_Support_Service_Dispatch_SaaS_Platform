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

    # 還原 dispatcher 密碼為 changeme123,避免污染其他測試 / demo 登入
    # （此為共用種子帳號;admin-reset 機制本身已於上方驗證）。
    import core.db as db_module
    from core.db import _ensure_conn

    assert await _ensure_conn()
    await db_module._conn.execute(
        "UPDATE users SET password_hash = %s WHERE email = %s",
        ("$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6", TARGET_EMAIL),
    )


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


@pytest.mark.asyncio
async def test_reset_technician_account_forbidden(client, admin_headers):
    """CR-0114 收斂:師傅帳號憑證歸平台方 → 品牌 admin 重設師傅密碼 403。

    師傅身分庫全平台唯一,品牌 admin 不可接管師傅登入憑證;師傅走自助
    忘記密碼(request-password-reset),平台方代重設為後續輪。
    """
    # 用 tech-chen@example.com（email 保持獨立的技師種子）—— 主技師 demo-tech
    # 的 email 已與 admin 統一為 test@lock-ai.com,而 admin_reset_password 依
    # (email, tenant) 查詢無 role 過濾,共用 email 會 LIMIT 1 誤中 admin 列而漏測。
    res = await client.post(
        RESET_PATH,
        headers=admin_headers,
        json={"email": "tech-chen@example.com"},  # SQL/seeds/technicians.sql 種子師傅
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "FORBIDDEN_TECHNICIAN_ACCOUNT"
