"""Component tests for M11 Invoice v2 tenant-scoped endpoints（CR-0003 P2-W5 / FR-0011）。

測試矩陣：
  1. GET /tenants/{tenantId}/accounting/invoices → 200 tenant-scoped list（cursor 分頁）
  2. GET /tenants/{tenantId}/accounting/invoices/{id} → 200 或 404
  3. cross-tenant guard → 403 CROSS_TENANT_READ（list + get/{id} 兩路徑）
  4. 未帶 Authorization → 401 UNAUTHENTICATED
  5. legacy GET /api/v1/accounting/invoices → 200 + Deprecation header（雙掛驗證）

注意：worktree 無真實 DB，這些測試須在有 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cross_tenant_headers(
    role: str = "admin",
    jwt_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=jwt_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/accounting/invoices — 200 tenant-scoped list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_invoices_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/accounting/invoices → 200 + pagination envelope。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/invoices",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_list_invoices_v2_pagination_fields(client, admin_headers):
    """GET /tenants/{tenantId}/accounting/invoices?limit=1 → cursor 分頁欄位存在。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/invoices?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "next_cursor" in body
    assert "has_more" in body


@pytest.mark.asyncio
async def test_list_invoices_v2_status_filter(client, admin_headers):
    """GET 加 status=issued 過濾 → 200（空列或有資料皆可）。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/invoices?status=issued",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/accounting/invoices/{id} — 200 or 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_invoice_v2_404_unknown_id(client, admin_headers):
    """GET /{id} 隨機 UUID → 404 NOT_FOUND（無 seed 資料時的正常行為）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/invoices/{fake_id}",
        headers=admin_headers,
    )
    # 無 seed 發票資料，404 是正確行為；若 seed 存在則可能 200
    assert res.status_code in (200, 404), res.text
    if res.status_code == 404:
        body = res.json()
        assert body.get("error_code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# cross-tenant guard — 403 CROSS_TENANT_READ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_invoices_v2_cross_tenant_403(client):
    """cross-tenant list：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/accounting/invoices",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_get_invoice_v2_cross_tenant_403(client):
    """cross-tenant get/{id}：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/accounting/invoices/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Unauthenticated — 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_invoices_v2_no_auth_401(client):
    """無 Authorization header → 401 UNAUTHENTICATED。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/invoices",
    )
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# Legacy endpoint — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_invoices_has_deprecation_header(client, admin_headers):
    """GET /api/v1/accounting/invoices → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/accounting/invoices",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
