"""CR-0143:角色指派 SoD 雙簽生產接線(WBS 2.1.2 收尾)。

service+DB CHECK 早於 CR-0071 存在(test_cr_0071_rbac_sod 覆蓋 service 層),
本檔測 HTTP 生產入口:提案/佇列/同人核准 403 SoD/異人核准即套用/拒絕/權限。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TENANT = "00000000-0000-0000-0000-000000000001"
BASE = f"/tenants/{TENANT}/role-assignments"


@pytest.fixture
def second_admin_headers() -> dict:
    """第二位 admin(不同 user_id;conftest 的 secondary_admin_headers 是 ops 非 admin)。"""
    from tests.conftest import _make_token

    token = _make_token(user_id="22222222-2222-4222-8222-222222222222", role="admin")
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT}


async def _mk_staff(role: str = "customer_service") -> str:
    assert await db_module._ensure_conn()
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, role) VALUES (%s::uuid, %s, %s, %s)",
        (uid, TENANT, f"ra-{uid[:8]}@example.com", role))
    return uid


async def _cleanup(uid: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM saas.role_assignment WHERE target_user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_propose_and_sod_same_person_403(client, admin_headers):
    uid = await _mk_staff()
    try:
        res = await client.post(BASE, json={
            "target_user_id": uid, "to_role": "reviewer", "reason": "職務調整"},
            headers=admin_headers)
        assert res.status_code == 201, res.text
        aid = res.json()["data"]["id"]

        # 同一 admin 核准自己的提案 → SoD 403
        res = await client.post(f"{BASE}/{aid}:approve", headers=admin_headers)
        assert res.status_code == 403
        assert res.json()["error_code"] == "SOD_VIOLATION_RBAC"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_second_admin_approve_applies_role(client, admin_headers,
                                                 second_admin_headers):
    uid = await _mk_staff()
    try:
        res = await client.post(BASE, json={
            "target_user_id": uid, "to_role": "operations_manager"},
            headers=admin_headers)
        aid = res.json()["data"]["id"]

        res = await client.post(f"{BASE}/{aid}:approve", headers=second_admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "applied"

        cur = await db_module._conn.execute(
            "SELECT role FROM users WHERE id=%s::uuid", (uid,))
        assert (await cur.fetchone())[0] == "operations_manager", "users.role 未套用"

        # 佇列查詢:applied 狀態可見
        res = await client.get(f"{BASE}?status=applied", headers=admin_headers)
        assert any(a["id"] == aid for a in res.json()["data"])
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_reject_flow(client, admin_headers, second_admin_headers):
    uid = await _mk_staff()
    try:
        res = await client.post(BASE, json={
            "target_user_id": uid, "to_role": "reviewer"}, headers=admin_headers)
        aid = res.json()["data"]["id"]

        res = await client.post(f"{BASE}/{aid}:reject",
                                json={"reason": "不需要"}, headers=admin_headers)
        assert res.status_code == 200 and res.json()["data"]["status"] == "rejected"

        # 已拒絕不可再核准
        res = await client.post(f"{BASE}/{aid}:approve", headers=second_admin_headers)
        assert res.status_code == 409

        # 角色未變
        cur = await db_module._conn.execute(
            "SELECT role FROM users WHERE id=%s::uuid", (uid,))
        assert (await cur.fetchone())[0] == "customer_service"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_non_admin_403_and_tenant_guard(client, admin_headers):
    from tests.conftest import _make_token

    uid = await _mk_staff()
    try:
        cs_headers = {
            "Authorization": f"Bearer {_make_token(user_id=str(uuid.uuid4()), role='customer_service')}",
            "X-Tenant-ID": TENANT,
        }
        res = await client.post(BASE, json={
            "target_user_id": uid, "to_role": "reviewer"}, headers=cs_headers)
        assert res.status_code == 403

        # 跨租戶 path 擋下
        other = f"/tenants/{uuid.uuid4()}/role-assignments"
        res = await client.get(other, headers=admin_headers)
        assert res.status_code == 403
    finally:
        await _cleanup(uid)
