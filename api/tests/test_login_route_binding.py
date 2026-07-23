"""登入路由綁定回歸測試（UAT-0723 P0 finding）。

背景：CR-0177 S3a 插入 `_set_login_cookie` helper 時，`@router.post("/auth/login")`
decorator 被黏到 helper 上、真正的 `login_admin` 未註冊——prod 上任何帳密打
/auth/login 都回 200 null（不驗證、不發 token），品牌後台自 0722 部署起登不進去。

本檔兩層守線：
1. 路由綁定內省——/auth/login 的 endpoint 必須是 login_admin（decorator 黏錯立即紅）。
2. client 級——mock auth_service.login 後打端點，斷言回 payload 非 null。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.component


def test_auth_routes_bound_to_real_handlers():
    """所有 auth 路由的 endpoint 函式名必須是 handler 本人（防 decorator 黏到 helper）。"""
    from routers import auth as auth_router

    expected = {
        "/auth/login": "login_admin",
        "/technicians/login": "login_technician",
        "/auth/refresh": "refresh_token",
    }
    bound = {r.path: r.endpoint.__name__ for r in auth_router.router.routes}
    for path, fn_name in expected.items():
        assert bound.get(path) == fn_name, (
            f"{path} 綁到 {bound.get(path)!r}（應為 {fn_name}）——decorator 黏錯函式"
        )


async def test_login_admin_returns_payload_not_null(client):
    """POST /api/v1/auth/login 必須回傳 auth_service.login 的 payload（曾整路回 null）。"""
    fake_payload = {
        "data": {
            "access_token": "tok-regression",
            "refresh_token": "r",
            "expires_in": 3600,
            "user": {"id": "u1", "role": "admin"},
        },
        "error": None,
    }
    with patch(
        "routers.auth.auth_service.login",
        new_callable=AsyncMock,
        return_value=fake_payload,
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "longenough123"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body is not None, "login 回 null——route decorator 黏錯（P0 回歸）"
    assert body["data"]["access_token"] == "tok-regression"
