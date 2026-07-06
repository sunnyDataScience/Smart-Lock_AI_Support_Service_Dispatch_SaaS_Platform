"""admin web 登入放寬收後台角色（CR-0021 Q2 / ADR-0111）整合測試。

驗證 /auth/login 收 admin/reviewer/operations_manager/dispatcher/customer_service;
technician 仍被擋（走 /technicians/login）。依賴 SQL/seeds/rbac_role_users.sql 種子帳號。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component

LOGIN = "/api/v1/auth/login"

# 後台角色種子帳號（password 全 changeme123）
BACKOFFICE = [
    "test@lock-ai.com",
    "dispatcher@example.com",
    "ops@example.com",
    "cs@example.com",
    "reviewer@example.com",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("email", BACKOFFICE)
async def test_backoffice_roles_can_login_admin_web(client, email):
    res = await client.post(LOGIN, json={"email": email, "password": "changeme123"})
    assert res.status_code == 200, f"{email} → {res.status_code}: {res.text}"
    assert res.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_technician_cannot_login_admin_web(client):
    # technician 走 /technicians/login;admin web login 應擋（401）。
    # 用 tech-chen@example.com（email 保持獨立的技師種子）—— 主技師 demo-tech 的
    # email 已與 admin 統一為 test@lock-ai.com,共用 email 會讓 admin-web 的
    # role 過濾查詢誤中 admin 列,故負向測試改用不共用 email 的技師。
    res = await client.post(
        LOGIN, json={"email": "tech-chen@example.com", "password": "changeme123"}
    )
    assert res.status_code == 401, res.text
