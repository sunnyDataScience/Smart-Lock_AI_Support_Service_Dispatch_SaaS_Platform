"""CR-0114 R3:平台方師傅審核端點(list + 生命週期 + audit)。

單庫 fallback:師傅住主連線;平台端點以 require_platform_admin 守衛
(token role=platform_admin,fixture 直接產,不需 seed)。品牌端 admin token
應被平台端點 403。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from tests.conftest import seed_required_kyc_docs  # CR-0195 核准需文件齊全

pytestmark = pytest.mark.component

PLATFORM_TECH = "/api/v1/platform/technicians"


async def _register(client) -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"plat-tech-{suffix}@example.com"
    password = "plat-tech-pw-123"
    resp = await client.post(
        "/api/v1/technicians/register",
        json={
            "name": f"平台審核測試{suffix}",
            "phone": f"09{int(suffix, 16) % 100000000:08d}",
            "email": email,
            "password": password,
            "service_areas": ["台北市"],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"], email, password


async def _cleanup(tech_id: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id=%s::uuid", (tech_id,))


@pytest.mark.asyncio
async def test_list_requires_platform_admin(client, admin_headers, platform_admin_headers):
    res = await client.get(PLATFORM_TECH)
    assert res.status_code == 401
    res = await client.get(PLATFORM_TECH, headers=admin_headers)
    assert res.status_code == 403, "品牌 admin 不可讀平台師傅清單"
    res = await client.get(PLATFORM_TECH, headers=platform_admin_headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_list_filter_and_search(client, platform_admin_headers):
    tech_id, email, _ = await _register(client)
    try:
        res = await client.get(
            f"{PLATFORM_TECH}?status=pending_approval", headers=platform_admin_headers)
        assert res.status_code == 200
        assert any(t["id"] == tech_id for t in res.json()["data"])

        res = await client.get(
            f"{PLATFORM_TECH}?q={email}", headers=platform_admin_headers)
        assert res.status_code == 200
        assert any(t["id"] == tech_id for t in res.json()["data"])
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_lifecycle_approve_suspend_reactivate_audit(client, platform_admin_headers):
    tech_id, _, _ = await _register(client)
    try:
        await seed_required_kyc_docs(tech_id)  # CR-0195：本測試驗生命週期，非文件閘
        # approve
        r = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve", json={},
            headers=platform_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["new_status"] == "active"

        # suspend（reason 必填）
        r = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:suspend",
            json={"reason": "平台停權測試"}, headers=platform_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["new_status"] == "suspended"

        # reactivate
        r = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:reactivate",
            json={"reason": "平台復權測試"}, headers=platform_admin_headers)
        assert r.status_code == 200, r.text

        # audit 事件（actor_role = platform_admin）
        r = await client.get(
            f"{PLATFORM_TECH}/lifecycle-events?tech_id={tech_id}",
            headers=platform_admin_headers)
        assert r.status_code == 200, r.text
        events = r.json()["data"]
        assert len(events) >= 3
        assert all(e["actor_role"] == "platform_admin" for e in events)
        types = {e["event_type"] for e in events}
        assert {"onboarding_approved", "suspended", "reactivated"} <= types
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_suspend_requires_reason(client, platform_admin_headers):
    tech_id, _, _ = await _register(client)
    try:
        await seed_required_kyc_docs(tech_id)  # CR-0195
        await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve", json={},
            headers=platform_admin_headers)
        r = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:suspend", json={"reason": "x"},
            headers=platform_admin_headers)
        assert r.status_code == 422, r.text
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_approve_nonexistent_404(client, platform_admin_headers):
    r = await client.post(
        f"{PLATFORM_TECH}/{uuid.uuid4()}:onboard-approve", json={},
        headers=platform_admin_headers)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_invalid_transition_409(client, platform_admin_headers):
    """pending_approval 直接 suspend → 409(狀態機不允許)。"""
    tech_id, _, _ = await _register(client)
    try:
        r = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:suspend",
            json={"reason": "非法轉移測試"}, headers=platform_admin_headers)
        assert r.status_code == 409, r.text
    finally:
        await _cleanup(tech_id)
