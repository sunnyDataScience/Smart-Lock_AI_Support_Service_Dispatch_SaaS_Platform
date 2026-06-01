"""Component tests for M17 vouchers v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/vouchers → 200 tenant-scoped list（cursor 分頁）
  2. cross-tenant guard → 403 CROSS_TENANT_READ
  3. legacy GET /api/v1/accounting/vouchers → 200 + Deprecation header（雙掛驗證）

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


def _make_other_tenant_path_headers(
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# List vouchers v2 — 200 tenant-scoped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_vouchers_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/vouchers → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/vouchers",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_list_vouchers_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/vouchers?limit=1 → cursor 分頁正常。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/vouchers?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "next_cursor" in body
    assert "has_more" in body


@pytest.mark.asyncio
async def test_list_vouchers_v2_posting_date_filter(client, admin_headers):
    """GET /tenants/{tenantId}/vouchers?posting_date_start=...&posting_date_end=... → 200。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/vouchers"
        "?posting_date_start=2026-01-01&posting_date_end=2026-12-31",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# cross-tenant guard — 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_vouchers_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/vouchers",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_export_voucher_v2_cross_tenant_403(client):
    """cross-tenant export → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/vouchers/{fake_id}/export",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Legacy endpoint — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_vouchers_has_deprecation_header(client, admin_headers):
    """GET /api/v1/accounting/vouchers → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/accounting/vouchers",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    link_header = res.headers.get("link", "")
    assert "successor-version" in link_header, (
        f"Expected Link header with successor-version, got: {link_header}"
    )
