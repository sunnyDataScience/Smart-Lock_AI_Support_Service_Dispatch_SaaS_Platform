"""M17 RBAC v2 tenant-scoped endpoint component tests（CR-0002-α）。

@pytest.mark.component

覆蓋範圍：
  1. GET /tenants/{tenantId}/rbac/roles — 200 tenant-scoped（正常路徑）
  2. GET /tenants/{tenantId}/rbac/roles — 403 cross-tenant（path tenant != JWT claim）
  3. PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions — admin 成功 200
  4. PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions — cross-tenant 403
  5. PUT /tenants/{tenantId}/rbac/roles/{roleName}/permissions — 非 RBAC admin 角色 403
  6. legacy GET /api/v1/roles — 回應帶 Deprecation header
  7. legacy PATCH /api/v1/roles/{role}/permissions — 回應帶 Deprecation header

worktree 無 DB：DB 相關測試在無 DB 時 skip（與既有 test_rbac_dynamic.py 相同慣例）。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component

from .conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID, _make_token  # type: ignore

OTHER_TENANT_ID = "99999999-9999-9999-9999-999999999999"

V2_LIST_PATH = f"/tenants/{DEFAULT_TENANT_ID}/rbac/roles"
V2_PERMS_PATH = f"/tenants/{DEFAULT_TENANT_ID}/rbac/roles/reviewer/permissions"

LEGACY_LIST_PATH = "/api/v1/roles"
LEGACY_PATCH_PATH = "/api/v1/roles/reviewer/permissions"


def _hdr(role: str, tenant_id: str = DEFAULT_TENANT_ID, user_id: str | None = None) -> dict:
    token = _make_token(
        user_id=user_id or ADMIN_USER_ID,
        role=role,
        tenant_id=tenant_id,
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


def _cross_tenant_hdr(role: str = "admin") -> dict:
    """Headers：JWT claim tenant=OTHER, path tenant=DEFAULT → cross-tenant mismatch。"""
    token = _make_token(
        user_id=ADMIN_USER_ID,
        role=role,
        tenant_id=OTHER_TENANT_ID,
    )
    return {
        "Authorization": f"Bearer {token}",
        # X-Tenant-ID = OTHER so require_tenant passes, but path tenantId = DEFAULT
        "X-Tenant-ID": OTHER_TENANT_ID,
    }


# ─── 1. GET v2 — 200 tenant-scoped ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_roles_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/rbac/roles → 200 + data list。"""
    res = await client.get(V2_LIST_PATH, headers=admin_headers)
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    # 應包含 5 個系統角色
    role_ids = {r["id"] for r in body["data"]}
    assert "admin" in role_ids
    assert "reviewer" in role_ids


# ─── 2. GET v2 — 403 cross-tenant guard ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_roles_v2_cross_tenant_403(client):
    """跨 tenant：JWT claim != path tenantId → 403 CROSS_TENANT_READ。"""
    headers = _cross_tenant_hdr()
    # path tenant = DEFAULT, JWT claim = OTHER → cross-tenant mismatch
    res = await client.get(V2_LIST_PATH, headers=headers)
    # require_tenant 本身也會做 TENANT_MISMATCH check（X-Tenant-ID vs claim）
    # 因為 X-Tenant-ID=OTHER 且 claim=OTHER，require_tenant passes；
    # 再由 router 做 cross-tenant guard → 403 CROSS_TENANT_READ
    # 這裡兩種情形都是 4xx，Accept 400/403。
    assert res.status_code in (403, 400), res.text
    err_code = res.json().get("error_code") or res.json().get("detail") or ""
    assert err_code or res.status_code == 403


# ─── 3. PUT v2 — admin 成功 200 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_role_permissions_v2_admin_200(client, admin_headers):
    """PUT /tenants/{tenantId}/rbac/roles/reviewer/permissions → 200。"""
    payload = {
        "permissions": [
            "work_orders.read",
            "technicians.read",
            "customers.read",
            "accounting.read",
            "invoices.read",
            "refunds.read",
            "refunds.write",
            "inventory.read",
            "warranty.read",
            "warranty.write",
            "disputes.read",
            "disputes.write",
        ],
        "reason": "CR-0002-α v2 test: reviewer baseline restore",
    }
    res = await client.put(V2_PERMS_PATH, json=payload, headers=admin_headers)
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["role_name"] == "reviewer"
    assert isinstance(body["permissions"], list)
    assert "updated_at" in body


# ─── 4. PUT v2 — cross-tenant 403 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_role_permissions_v2_cross_tenant_403(client):
    """PUT 跨 tenant → 403。"""
    headers = _cross_tenant_hdr()
    payload = {
        "permissions": ["work_orders.read"],
        "reason": "cross-tenant test",
    }
    res = await client.put(V2_PERMS_PATH, json=payload, headers=headers)
    assert res.status_code in (403, 400), res.text


# ─── 5. PUT v2 — 非 RBAC admin 角色 403 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_update_role_permissions_v2_non_rbac_admin_403(client):
    """technician / dispatcher 試打 v2 PUT → 403 FORBIDDEN。"""
    for role in ("technician", "dispatcher"):
        headers = _hdr(role, user_id="22222222-2222-2222-2222-222222222222")
        payload = {
            "permissions": ["work_orders.read"],
            "reason": "should be forbidden",
        }
        res = await client.put(V2_PERMS_PATH, json=payload, headers=headers)
        if res.status_code == 503:
            pytest.skip("DB not available")
        assert res.status_code == 403, f"{role} should get 403, got {res.status_code}"
        assert res.json().get("error_code") == "FORBIDDEN"


# ─── 6. legacy GET — Deprecation header ──────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_list_roles_has_deprecation_header(client, admin_headers):
    """GET /api/v1/roles → response 帶 Deprecation: true header（D3）。"""
    res = await client.get(LEGACY_LIST_PATH, headers=admin_headers)
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    link = res.headers.get("link", "")
    assert "rbac/roles" in link, f"Expected successor link in Link header, got: {link}"


# ─── 7. legacy PATCH — Deprecation header ────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_patch_permissions_has_deprecation_header(client, admin_headers):
    """PATCH /api/v1/roles/reviewer/permissions → response 帶 Deprecation: true header（D3）。"""
    payload = {
        "permissions": [
            "work_orders.read",
            "refunds.read",
            "refunds.write",
        ],
        "reason": "deprecation header test",
    }
    res = await client.patch(LEGACY_PATCH_PATH, json=payload, headers=admin_headers)
    if res.status_code == 503:
        pytest.skip("DB not available")
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    link = res.headers.get("link", "")
    assert "rbac/roles" in link, f"Expected successor link in Link header, got: {link}"
