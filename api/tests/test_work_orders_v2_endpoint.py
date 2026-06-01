"""Component tests for M06 work-orders v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET  /tenants/{tenantId}/work-orders        → 200 tenant-scoped list（cursor 分頁）
  2. GET  /tenants/{tenantId}/work-orders/{id}   → 404 not found（DB 無 seed WO）
  3. POST /tenants/{tenantId}/work-orders        → 建立工單（帶 Idempotency-Key）
  4. cross-tenant GET guard                      → 403 CROSS_TENANT_READ
  5. cross-tenant POST guard                     → 403 CROSS_TENANT_WRITE
  6. legacy GET /api/v1/work-orders              → 200 + Deprecation header（D3 雙掛驗證）

注意：worktree 無真實 DB，這些測試須在有 DB 的環境跑（@pytest.mark.component）。
      cross-tenant 403 可在無 DB 時就在 guard 層 early-return，故在 CI 可跑。
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


def _make_idem_headers(base: dict[str, str]) -> dict[str, str]:
    """在現有 headers 基礎上加新鮮 Idempotency-Key（POST 必須帶）。"""
    return {**base, "Idempotency-Key": str(uuid.uuid4())}


# ---------------------------------------------------------------------------
# List work-orders v2 — GET /tenants/{tenantId}/work-orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_work_orders_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/work-orders → 200 tenant-scoped list（含 items / has_more 欄位）。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body


@pytest.mark.asyncio
async def test_list_work_orders_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/work-orders?limit=1 → cursor 分頁結構正確。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body


@pytest.mark.asyncio
async def test_list_work_orders_v2_cross_tenant_403(client):
    """cross-tenant read：path tenantId ≠ JWT claim → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/work-orders",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Get work-order v2 — GET /tenants/{tenantId}/work-orders/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_work_order_v2_not_found(client, admin_headers):
    """GET 不存在的工單 → 404（DB 無 seed WO）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_get_work_order_v2_cross_tenant_403(client):
    """cross-tenant get：path tenantId ≠ JWT claim → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Create work-order v2 — POST /tenants/{tenantId}/work-orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_work_order_v2_requires_idempotency_key(client, admin_headers):
    """POST /tenants/{tenantId}/work-orders 缺 Idempotency-Key → 400（idempotency_guard）。"""
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders",
        headers=admin_headers,  # 無 Idempotency-Key
        json={"problem_card_id": str(uuid.uuid4())},
    )
    # idempotency_guard 缺 key → 400 先於 403/404
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_create_work_order_v2_not_found_pc(client, admin_headers):
    """POST 帶 Idempotency-Key 但 problem_card_id 不存在 → 404。"""
    headers = _make_idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders",
        headers=headers,
        json={"problem_card_id": str(uuid.uuid4())},
    )
    # DB 無此 PC → 404（service 層 NOT_FOUND）
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_create_work_order_v2_cross_tenant_403(client):
    """cross-tenant create：path tenantId ≠ JWT claim → 403 CROSS_TENANT_WRITE。"""
    headers = _make_idem_headers(_make_other_tenant_path_headers())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders",
        headers=headers,
        json={"problem_card_id": str(uuid.uuid4())},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# State-machine action guards — cross-tenant 403 checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_work_order_v2_cross_tenant_403(client):
    """POST .../work-orders/{id}:accept cross-tenant → 403 CROSS_TENANT_WRITE。"""
    headers = _make_idem_headers(_make_other_tenant_path_headers())
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}:accept",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_complete_work_order_v2_cross_tenant_403(client):
    """POST .../work-orders/{id}:complete cross-tenant → 403 CROSS_TENANT_WRITE。"""
    headers = _make_idem_headers(_make_other_tenant_path_headers())
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}:complete",
        headers=headers,
        json={"summary": "test completion report x10chars", "photos_before": [], "photos_after": []},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Legacy dual-hang — GET /api/v1/work-orders → Deprecation header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_work_orders_has_deprecation_header(client, admin_headers):
    """GET /api/v1/work-orders → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/work-orders",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 保證）。
    # Link successor-version 為 per-route 選配；本波依規則不改 legacy router，故不硬性要求。
