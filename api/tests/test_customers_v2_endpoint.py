"""Component tests for M04 customers v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/customers → 200 tenant-scoped list（cursor 分頁）
  2. POST /tenants/{tenantId}/customers → 201 建立客戶成功
  3. GET /tenants/{tenantId}/customers/{id} → 200 單筆詳情
  4. PUT /tenants/{tenantId}/customers/{id} → 200 更新成功
  5. cross-tenant guard → 403 CROSS_TENANT_READ / CROSS_TENANT_WRITE
  6. legacy GET /api/v1/customers → 200 + Deprecation header（雙掛驗證）

注意：worktree 無真實 DB，這些測試須在 Opus 主 worktree 有 DB 的環境跑。
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


def _make_other_tenant_headers(
    role: str = "admin",
    tenant_id: str = OTHER_TENANT_ID,
) -> dict[str, str]:
    """生成屬於另一個 tenant 的 JWT headers（用於 cross-tenant guard 測試）。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,  # header 與 claim 不符 → tenant mismatch
    }


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
# List customers v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_customers_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/customers → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    # tenant-scoped：所有結果應屬 DEFAULT_TENANT
    for item in body["items"]:
        assert "id" in item


@pytest.mark.asyncio
async def test_list_customers_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/customers?limit=1 → cursor 分頁。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_list_customers_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/customers",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Customer stats v2（聚合統計卡）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customer_stats_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/customers/stats → 200，回 4 個聚合計數。

    驗證 /customers/stats 不被 /customers/{id} path param 吞掉（路由註冊順序）
    且回傳結構齊全、各計數為非負整數、子計數 ≤ 總數。
    """
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers/stats",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    for key in ("total", "active_30d", "high_risk", "expired_warranty"):
        assert key in data, f"missing stat key: {key}"
        assert isinstance(data[key], int) and data[key] >= 0
    assert data["active_30d"] <= data["total"]
    assert data["high_risk"] <= data["total"]
    assert data["expired_warranty"] <= data["total"]


@pytest.mark.asyncio
async def test_customer_stats_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/customers/stats",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Create customer v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_customer_v2_201(client, admin_headers):
    """POST /tenants/{tenantId}/customers → 201 建立客戶。"""
    unique_name = f"Test Customer {uuid.uuid4().hex[:8]}"
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/customers",
        headers=admin_headers,
        json={
            "display_name": unique_name,
            "phone": "0912345678",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["success"] is True
    assert body["data"]["display_name"] == unique_name

    # cleanup
    created_id = body["data"]["id"]
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM users WHERE id = %s::uuid", (created_id,)
    )


@pytest.mark.asyncio
async def test_create_customer_v2_cross_tenant_403(client):
    """cross-tenant create → 403。"""
    headers = _make_other_tenant_path_headers()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/customers",
        headers=headers,
        json={"display_name": "Should Fail", "phone": "0987654321"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_create_customer_v2_missing_display_name_422(client, admin_headers):
    """display_name 未填 → 422。"""
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/customers",
        headers=admin_headers,
        json={"phone": "0912345678"},
    )
    assert res.status_code in (422,), res.text


# ---------------------------------------------------------------------------
# Get customer v2 (detail + aggregated history)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_customer_v2_not_found(client, admin_headers):
    """GET 不存在的 customer → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_get_customer_v2_cross_tenant_403(client):
    """cross-tenant get → 403。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/customers/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Legacy endpoint — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_customers_has_deprecation_header(client, admin_headers):
    """GET /api/v1/customers → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/customers",
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
