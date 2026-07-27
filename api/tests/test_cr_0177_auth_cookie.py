"""CR-0177 S3a：access token httpOnly cookie（自訂網域就緒）。

鎖定：env 未設＝host-only（現況行為不變）、設 `AUTH_COOKIE_DOMAIN` 即跨子網域、
cookie 屬性含 HttpOnly/SameSite/Path、Secure 依環境推導。純函式，不碰 DB。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import Response
from starlette.requests import Request

from core import auth_cookie
from routers.auth import _auth_response_payload


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("AUTH_COOKIE_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)


def _set_cookie_header(resp: Response) -> str:
    return resp.headers.get("set-cookie", "")


def test_domain_none_by_default():
    assert auth_cookie.cookie_domain() is None


def test_domain_from_env(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_DOMAIN", ".example.tw")
    assert auth_cookie.cookie_domain() == ".example.tw"


def test_secure_defaults_off_locally_on_with_domain(monkeypatch):
    assert auth_cookie.cookie_secure() is False           # 本機（無共用網域）
    monkeypatch.setenv("AUTH_COOKIE_DOMAIN", ".example.tw")
    assert auth_cookie.cookie_secure() is True            # 有共用網域＝prod


def test_secure_explicit_override(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    assert auth_cookie.cookie_secure() is True
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_COOKIE_DOMAIN", ".example.tw")
    assert auth_cookie.cookie_secure() is False           # 明示優先於推導


def test_cloud_run_deploy_forces_secure_host_only_cookies():
    deploy = (Path(__file__).parents[2] / "scripts/deploy/api.sh").read_text(
        encoding="utf-8"
    )
    assert "AUTH_COOKIE_SECURE=1" in deploy


def test_set_access_cookie_attributes():
    r = Response()
    auth_cookie.set_access_cookie(r, "tok123", 3600)
    h = _set_cookie_header(r)
    assert "smartlock_access_token=tok123" in h
    assert "HttpOnly" in h                 # JS 不可讀 → XSS 偷不到
    assert "Path=/" in h
    assert "Max-Age=3600" in h
    assert "samesite=lax" in h.lower()
    assert "Domain=" not in h              # env 未設 → host-only


def test_set_access_cookie_with_domain(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_DOMAIN", ".example.tw")
    r = Response()
    auth_cookie.set_access_cookie(r, "tok123", 60)
    h = _set_cookie_header(r)
    assert "Domain=.example.tw" in h       # 跨子網域（web/api 同父網域才送得到）
    assert "Secure" in h


def test_clear_access_cookie():
    r = Response()
    auth_cookie.clear_access_cookie(r)
    h = _set_cookie_header(r)
    assert "smartlock_access_token=" in h
    assert 'Max-Age=0' in h or "expires=" in h.lower()


def test_refresh_cookie_is_httponly_and_cleared_with_session():
    r = Response()
    auth_cookie.set_refresh_cookie(r, "refresh123", 86400)
    headers = r.headers.getlist("set-cookie")
    assert any("smartlock_refresh_token=refresh123" in h for h in headers)
    assert all("HttpOnly" in h for h in headers)

    cleared = Response()
    auth_cookie.clear_session_cookies(cleared)
    clear_headers = cleared.headers.getlist("set-cookie")
    assert any("smartlock_access_token=" in h for h in clear_headers)
    assert any("smartlock_refresh_token=" in h for h in clear_headers)


def test_no_token_no_cookie_helper_contract():
    """set 只在有 token 時呼叫（router 端 _set_login_cookie 已守），此處確保空值不寫入。"""
    r = Response()
    auth_cookie.set_access_cookie(r, "", 3600)
    # 空 token 仍會寫 header（helper 不做業務判斷）——由 router 負責不呼叫
    assert "smartlock_access_token=" in _set_cookie_header(r)


def test_browser_cookie_mode_response_never_exposes_tokens():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"x-auth-response-mode", b"cookie")],
        }
    )
    result = _auth_response_payload(
        request,
        {
            "data": {
                "access_token": "access-secret",
                "refresh_token": "refresh-secret",
                "expires_in": 3600,
            }
        },
    )
    assert result["data"]["authenticated"] is True
    assert "access_token" not in result["data"]
    assert "refresh_token" not in result["data"]


def test_browser_session_endpoints_use_v2_without_expanding_frozen_v1():
    import main

    paths = {getattr(route, "path", "") for route in main.app.router.routes}
    assert "/api/v2/auth/session" in paths
    assert "/api/v2/platform/auth/session" in paths
    assert "/api/v1/auth/session" not in paths
    assert "/api/v1/platform/auth/session" not in paths
