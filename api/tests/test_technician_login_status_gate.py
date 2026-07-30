"""技師登入狀態閘（2026-07-02 師傅端測試修復）。

Root cause：technicians.status（生命週期）與 users.is_active（登入檢查點）脫鉤——
register 以 is_active=TRUE 建 user、lifecycle 只改 technicians.status →
待核准/停權技師仍可登入（違反 BR-M07-01 上線審核 gate + beta checklist A6 語意）。

驗證閉環：register → 登入 403 待核准 → 核准 → 登入 200 → 停權 → 登入 403 已停權
→ 復權 → 登入 200。全走 HTTP 端點（含 lifecycle 的 users.is_active 同步）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from tests.conftest import seed_required_kyc_docs  # CR-0195 核准需文件齊全

TENANT = "00000000-0000-0000-0000-000000000001"


async def _register(client) -> tuple[str, str, str]:
    """自助註冊一位技師。回 (tech_id, email, password)。"""
    suffix = uuid.uuid4().hex[:8]
    email = f"login-gate-{suffix}@example.com"
    password = "gate-pass-123"
    resp = await client.post(
        "/api/v1/technicians/register",
        json={
            "name": f"登入閘測試技師{suffix}",
            "phone": f"09{int(suffix, 16) % 100000000:08d}",
            "email": email,
            "password": password,
            "service_areas": ["台北市信義區"],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code in (200, 201), resp.text
    tech_id = resp.json()["data"]["id"]
    return tech_id, email, password


async def _login(client, email: str, password: str):
    return await client.post(
        "/api/v1/technicians/login",
        json={"identifier": email, "password": password},
    )


async def _cleanup(tech_id: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid",
        (tech_id,),
    )
    await db_module._conn.execute(
        "DELETE FROM users WHERE id = "
        "(SELECT user_id FROM technicians WHERE id=%s::uuid)",
        (tech_id,),
    )
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id=%s::uuid", (tech_id,)
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_full_lifecycle_login_gate(client, platform_admin_headers):
    # CR-0114 R3:生命週期審核已搬平台方 → 打 /api/v1/platform/technicians（無
    # tenant scope、無 X-Initiator;initiator 取 token sub）。
    tech_id, email, password = await _register(client)
    try:
        # 1) 待核准 → 403 + 精確錯誤碼
        r = await _login(client, email, password)
        assert r.status_code == 403, r.text
        assert r.json()["error_code"] == "ACCOUNT_PENDING_APPROVAL"

        # 2) 核准 → 可登入（CR-0195：核准需文件齊全，本測試驗登入閘非文件閘）
        await seed_required_kyc_docs(tech_id)
        r = await client.post(
            f"/api/v1/platform/technicians/{tech_id}:onboard-approve",
            json={}, headers=platform_admin_headers,
        )
        assert r.status_code == 200, r.text
        r = await _login(client, email, password)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["access_token"]

        # 3) 停權 → 403 + 精確錯誤碼
        r = await client.post(
            f"/api/v1/platform/technicians/{tech_id}:suspend",
            json={"reason": "登入閘測試停權"},
            headers=platform_admin_headers,
        )
        assert r.status_code == 200, r.text
        r = await _login(client, email, password)
        assert r.status_code == 403, r.text
        assert r.json()["error_code"] == "ACCOUNT_SUSPENDED"

        # 4) 復權 → 恢復登入
        r = await client.post(
            f"/api/v1/platform/technicians/{tech_id}:reactivate",
            json={"reason": "登入閘測試復權"},
            headers=platform_admin_headers,
        )
        assert r.status_code == 200, r.text
        r = await _login(client, email, password)
        assert r.status_code == 200, r.text
    finally:
        await _cleanup(tech_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_register_creates_inactive_user(client):
    tech_id, _email, _password = await _register(client)
    try:
        assert await db_module._ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT u.is_active FROM users u "
            "JOIN technicians t ON t.user_id = u.id WHERE t.id=%s::uuid",
            (tech_id,),
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is False  # 待核准前不可登入
    finally:
        await _cleanup(tech_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_terminate_blocks_login(client, platform_admin_headers):
    tech_id, email, password = await _register(client)
    try:
        await seed_required_kyc_docs(tech_id)  # CR-0195：本測試驗登入閘非文件閘
        r = await client.post(
            f"/api/v1/platform/technicians/{tech_id}:onboard-approve",
            json={}, headers=platform_admin_headers,
        )
        assert r.status_code == 200
        r = await client.post(
            f"/api/v1/platform/technicians/{tech_id}:terminate",
            json={"reason": "登入閘測試終止"},
            headers=platform_admin_headers,
        )
        assert r.status_code == 200, r.text
        r = await _login(client, email, password)
        assert r.status_code == 403, r.text
        assert r.json()["error_code"] == "ACCOUNT_DISABLED"  # terminated → 一般停用訊息
    finally:
        await _cleanup(tech_id)
