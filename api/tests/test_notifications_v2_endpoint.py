"""Component tests for notifications v2 tenant-scoped endpoints（CR-0003 P2-W2 / ADR-0012）。

測試矩陣：
  1. GET  /tenants/{tenantId}/notifications → 200（含 items key）
  2. PATCH /tenants/{tenantId}/notifications/{id} → 200 / 404 / 503（強制 Idempotency-Key）
  3. POST /tenants/{tenantId}/notifications:bulk → 200 / 503（帶 Idempotency-Key）
  4. POST /tenants/{tenantId}/notifications:mark-all-read → 200 / 503（帶 Idempotency-Key）
  5. cross-tenant GET guard → 403 CROSS_TENANT_READ
  6. cross-tenant PATCH guard → 403 CROSS_TENANT_WRITE
  7. cross-tenant POST bulk guard → 403 CROSS_TENANT_WRITE
  8. cross-tenant POST mark-all-read guard → 403 CROSS_TENANT_WRITE

注意：worktree 無真實 DB，服務函式可能回 503（DB unavailable）或 404（not found）。
      cross-tenant guard 在 service 呼叫前執行，無 DB 也能確保 403。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.unit

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cross_tenant_headers(
    role: str = "admin",
    own_tenant: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=own_tenant,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_notifications_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/notifications → 200（含 items key）或 DB unavailable。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications",
        headers=admin_headers,
    )
    # 無 DB 時 503；有 DB 時 200
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body


@pytest.mark.asyncio
async def test_list_notifications_v2_cross_tenant_403(client):
    """cross-tenant GET：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/notifications",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# PATCH /tenants/{tenantId}/notifications/{notificationId}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_notification_v2(client, admin_headers):
    """PATCH /tenants/{tenantId}/notifications/{id} → 200 / 404 / 503（帶穩定 action key）。"""
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications/{fake_id}",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"read_at": "2026-06-01T12:00:00Z"},
    )
    # 無 DB → 503；有 DB 但 id 不存在 → 404；存在 → 200
    assert res.status_code in (200, 404, 503), res.text


@pytest.mark.asyncio
async def test_update_notification_v2_cross_tenant_403(client):
    """cross-tenant PATCH → 403 CROSS_TENANT_WRITE。"""
    headers = _make_cross_tenant_headers()
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{OTHER_TENANT_ID}/notifications/{fake_id}",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"read_at": "2026-06-01T12:00:00Z"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_update_notification_v2_missing_action_key_400(client, admin_headers):
    """ADR-034：PATCH 缺 action id 不得執行，避免 retry 時產生第二次 mutation。"""
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications/{fake_id}",
        headers=admin_headers,
        json={"read_at": "2026-06-01T12:00:00Z"},
    )
    assert res.status_code == 400, res.text
    assert res.json()["error_code"] == "MISSING_IDEMPOTENCY_KEY"


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/notifications:bulk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_update_notifications_v2(client, admin_headers):
    """POST /tenants/{tenantId}/notifications:bulk → 200 / 503（帶 Idempotency-Key）。"""
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications:bulk",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "ids": [str(uuid.uuid4())],
            "action": "mark_read",
        },
    )
    # 無 DB → 503；有 DB → 200
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "affected" in body


@pytest.mark.asyncio
async def test_bulk_update_notifications_v2_cross_tenant_403(client):
    """cross-tenant POST bulk → 403 CROSS_TENANT_WRITE。"""
    headers = _make_cross_tenant_headers()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/notifications:bulk",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "ids": [str(uuid.uuid4())],
            "action": "archive",
        },
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/notifications:mark-all-read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_all_notifications_read_v2(client, admin_headers):
    """POST /tenants/{tenantId}/notifications:mark-all-read → 200 / 503（帶 Idempotency-Key）。"""
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications:mark-all-read",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    # 無 DB → 503；有 DB → 200
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "affected" in body


@pytest.mark.asyncio
async def test_mark_all_notifications_read_v2_with_filter(client, admin_headers):
    """POST mark-all-read 帶 type filter → 200 / 503。"""
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/notifications:mark-all-read",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"filter": {"type": ["work_order", "sla"]}},
    )
    assert res.status_code in (200, 503), res.text


@pytest.mark.asyncio
async def test_mark_all_notifications_read_v2_cross_tenant_403(client):
    """cross-tenant POST mark-all-read → 403 CROSS_TENANT_WRITE。"""
    headers = _make_cross_tenant_headers()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/notifications:mark-all-read",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"
