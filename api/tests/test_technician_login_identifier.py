"""技師登入支援「手機號或 Email」（CR-0099）整合 + 守門測試。

驗證：
  - 手機號（09xxxxxxxx）登入 → 200（demo-tech 種子 phone=0911222333）
  - Email 登入 → 200（既有路徑不回歸）
  - 密碼錯 → 401；查無手機 → 401
  - 手機對應多帳號 → 409 AMBIGUOUS_IDENTIFIER（§8.1，monkeypatch 模擬非唯一）
依賴 SQL/seeds/technicians.sql 的 demo-tech@example.com / techpass123 / 0911222333。
"""

from __future__ import annotations

import pytest

from services import auth_service

pytestmark = pytest.mark.component

TECH_LOGIN = "/api/v1/technicians/login"
DEMO_PHONE = "0911222333"
DEMO_EMAIL = "demo-tech@example.com"
DEMO_PASS = "techpass123"


@pytest.mark.asyncio
async def test_technician_login_by_phone(client):
    res = await client.post(TECH_LOGIN, json={"identifier": DEMO_PHONE, "password": DEMO_PASS})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_technician_login_by_email_still_works(client):
    res = await client.post(TECH_LOGIN, json={"identifier": DEMO_EMAIL, "password": DEMO_PASS})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_technician_login_wrong_password_401(client):
    res = await client.post(TECH_LOGIN, json={"identifier": DEMO_PHONE, "password": "wrongpass1"})
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_technician_login_unknown_phone_401(client):
    res = await client.post(TECH_LOGIN, json={"identifier": "0900000000", "password": DEMO_PASS})
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_technician_login_ambiguous_phone_409(client, monkeypatch):
    """手機對應多帳號（種子無此情境，monkeypatch 模擬）→ 409，要求改用 Email。"""

    async def _two_matches(phone, role_in):
        base = {"password_hash": "x", "role": "technician",
                "tenant_id": "00000000-0000-0000-0000-000000000001", "is_active": True}
        return [{"id": "a", "email": "a@x.com", **base},
                {"id": "b", "email": "b@x.com", **base}]

    monkeypatch.setattr(auth_service, "_find_users_by_phone", _two_matches)
    res = await client.post(TECH_LOGIN, json={"identifier": DEMO_PHONE, "password": DEMO_PASS})
    assert res.status_code == 409, res.text
    assert res.json()["error_code"] == "AMBIGUOUS_IDENTIFIER"
