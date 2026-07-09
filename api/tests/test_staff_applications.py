"""CR-0114 R5:品牌員工帳號申請(登入頁申請 → 品牌 Admin 審核指派角色)。

品牌庫表 staff_applications(migration 088)。每測試自清資料。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TENANT = "00000000-0000-0000-0000-000000000001"
SUBMIT = f"/tenants/{TENANT}/staff-applications"  # 公開 submit 與審核同前綴(tenant-scoped)
# 清理用全集（含保留角色 dispatcher 的存量測試殘留）；可開通集合見 _STAFF_ROLES（4 值，SA-06）
_ROLES = ["operations_manager", "dispatcher", "customer_service", "reviewer", "admin"]


def _tenant_headers() -> dict:
    # submit 為公開端點(tenantId 取自 path),不需 X-Tenant-ID;保留空 headers helper
    return {}


def _payload(**over) -> dict:
    return {
        "name": "測試員工",
        "email": f"staff-{uuid.uuid4().hex[:8]}@brand-example.com",
        "phone": "0912345678",
        "password": "staff-pass-123",
        **over,
    }


async def _cleanup(email: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM staff_applications WHERE email = %s", (email,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE email = %s AND role = ANY(%s)", (email, _ROLES))


# ── 公開申請 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_public_201(client):
    body = _payload()
    try:
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        assert res.status_code == 201, res.text
        assert res.json()["data"]["status"] == "pending"
    finally:
        await _cleanup(body["email"])


@pytest.mark.asyncio
async def test_submit_duplicate_pending_409(client):
    body = _payload()
    try:
        assert (await client.post(SUBMIT, json=body, headers=_tenant_headers())).status_code == 201
        res = await client.post(SUBMIT, json={**body, "name": "另一人"}, headers=_tenant_headers())
        assert res.status_code == 409, res.text
    finally:
        await _cleanup(body["email"])


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("password", "short"), ("email", "not-an-email"), ("name", "")])
async def test_submit_validation_422(client, field, value):
    res = await client.post(SUBMIT, json=_payload(**{field: value}))
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_submit_does_not_create_user(client):
    """裁決 4:申請階段不建 users(不選角色,由 Admin 指派)。"""
    body = _payload()
    try:
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        assert res.status_code == 201
        assert await db_module._ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = %s", (body["email"],))
        assert (await cur.fetchone())[0] == 0, "申請階段不該建 users"
    finally:
        await _cleanup(body["email"])


# ── 審核(品牌 Admin)────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_requires_full_access(client, admin_headers, dispatcher_headers):
    res = await client.get(f"/tenants/{TENANT}/staff-applications")
    assert res.status_code in (401, 403)
    res = await client.get(f"/tenants/{TENANT}/staff-applications", headers=dispatcher_headers)
    assert res.status_code == 403, "dispatcher 非 FULL_ACCESS,不可審員工申請"
    res = await client.get(f"/tenants/{TENANT}/staff-applications", headers=admin_headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_approve_assigns_role_and_creates_user(client, admin_headers):
    body = _payload()
    try:
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        app_id = res.json()["data"]["id"]

        res = await client.post(
            f"/tenants/{TENANT}/staff-applications/{app_id}:approve",
            json={"role": "operations_manager"}, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["assigned_role"] == "operations_manager"

        # 核准後可用該密碼登入(role=operations_manager,is_active=TRUE)
        login = await client.post(
            "/api/v1/auth/login", json={"email": body["email"], "password": body["password"]})
        assert login.status_code == 200, "核准後應可登入"
        # 再核准同申請 → 409(非 pending)
        res = await client.post(
            f"/tenants/{TENANT}/staff-applications/{app_id}:approve",
            json={"role": "operations_manager"}, headers=admin_headers)
        assert res.status_code == 409
    finally:
        await _cleanup(body["email"])


@pytest.mark.asyncio
async def test_approve_invalid_role_422(client, admin_headers):
    body = _payload()
    try:
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        app_id = res.json()["data"]["id"]
        res = await client.post(
            f"/tenants/{TENANT}/staff-applications/{app_id}:approve",
            json={"role": "super_admin"}, headers=admin_headers)
        assert res.status_code == 422, "super_admin 為死角色，不在可開通集合"
        # dispatcher 為保留角色（13_Security §3.1，SA-06）——核准指派同樣 422
        res = await client.post(
            f"/tenants/{TENANT}/staff-applications/{app_id}:approve",
            json={"role": "dispatcher"}, headers=admin_headers)
        assert res.status_code == 422, "dispatcher 保留角色不可開通"
    finally:
        await _cleanup(body["email"])


@pytest.mark.asyncio
async def test_reject_then_can_reapply(client, admin_headers):
    body = _payload()
    try:
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        app_id = res.json()["data"]["id"]
        res = await client.post(
            f"/tenants/{TENANT}/staff-applications/{app_id}:reject",
            json={"reason": "資料不符,請補部門資訊"}, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "rejected"
        # 拒絕後同 email 可再申請(部分唯一索引只鎖 pending)
        res = await client.post(SUBMIT, json=body, headers=_tenant_headers())
        assert res.status_code == 201
    finally:
        await _cleanup(body["email"])
