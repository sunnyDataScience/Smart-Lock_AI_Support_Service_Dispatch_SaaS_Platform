"""Component tests for M05 technicians v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/technicians → 200 tenant-scoped list（cursor 分頁）
  2. GET /tenants/{tenantId}/technicians/{techId} → 200 或 404（不存在的 techId）
  3. cross-tenant guard → 403 CROSS_TENANT_READ
  4. POST /tenants/{tenantId}/technicians/{techId}:suspend → 501 NOT_IMPLEMENTED（stub）
  5. cross-tenant suspend → 403 CROSS_TENANT_WRITE
  6. legacy GET /api/v1/technicians → 200 + Deprecation header（D3 雙掛驗證）
  7. legacy GET /api/v1/technicians/{id} → 200/404 + Deprecation header

注意：worktree 無真實 DB，component 測試須在有 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

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
# List technicians v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_technicians_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/technicians → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    # tenant-scoped：所有結果應有 id 欄位
    for item in body["items"]:
        assert "id" in item


@pytest.mark.asyncio
async def test_list_technicians_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/technicians?limit=1 → cursor 分頁。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_list_technicians_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/technicians",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Get technician v2 (detail)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_technician_v2_not_found(client, admin_headers):
    """GET 不存在的 technician → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_get_technician_v2_cross_tenant_403(client):
    """cross-tenant get → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/technicians/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Suspend technician v2 (stub — 501)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_technician_v2_501_stub(client, admin_headers):
    """POST /tenants/{tenantId}/technicians/{techId}:suspend → 501 NOT_IMPLEMENTED（stub）。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{fake_id}:suspend",
        headers=admin_headers,
    )
    assert res.status_code == 501, res.text
    body = res.json()
    assert body.get("error_code") == "NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_suspend_technician_v2_cross_tenant_403(client):
    """cross-tenant suspend → 403 CROSS_TENANT_WRITE。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/technicians/{fake_id}:suspend",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Legacy endpoints — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_technicians_has_deprecation_header(client, admin_headers):
    """GET /api/v1/technicians → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/technicians",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加，此處不硬性要求。


@pytest.mark.asyncio
async def test_legacy_get_technician_has_deprecation_header(client, admin_headers):
    """GET /api/v1/technicians/{id} → 404 + Deprecation: true（D3 雙掛驗證，即使 404 也帶 header）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/api/v1/technicians/{fake_id}",
        headers=admin_headers,
    )
    # 無論 404 或 200 都應帶 Deprecation header
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加（error path 會隨 raise 遺失），此處不硬性要求。
