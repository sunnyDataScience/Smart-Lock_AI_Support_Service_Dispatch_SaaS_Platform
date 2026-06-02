"""Component tests — Sentiment Alerts v2 tenant-scoped（CR-0003 P2-W2 / FR-0018 / ADR-0048）。

測試矩陣：
  1. GET  /tenants/{tenantId}/sentiment/alerts        → 200（含 SentimentAlertPage 結構）；無 DB 時接受 503
  2. PATCH /tenants/{tenantId}/sentiment/alerts/{id}  → 200（Idempotency-Key，依 W1 教訓）；無 DB 時接受 404/503
  3. cross-tenant GET  → 403 CROSS_TENANT_READ
  4. cross-tenant PATCH → 403 CROSS_TENANT_WRITE
  5. 未認證 GET  → 401
  6. 未認證 PATCH → 401

注意：
  - 無真實 DB 時 200 路徑可能回 503（DB unavailable）；
    cross-tenant guard 在 DB 查詢前執行，因此 403 路徑不依賴 DB。
  - PATCH 測試必須帶 Idempotency-Key header（W1 教訓）。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.unit

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cross_tenant_headers(
    role: str = "admin",
    own_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT claim 屬 own_tenant，但打 OTHER_TENANT path → cross-tenant guard 觸發。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=own_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": own_tenant_id,
    }


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/sentiment/alerts — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sentiment_alerts_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/sentiment/alerts → 200（含 SentimentAlertPage 結構）；無 DB 時接受 503。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/sentiment/alerts",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        # SentimentAlertPage schema 驗證
        assert "items" in body
        assert "has_more" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["has_more"], bool)


@pytest.mark.asyncio
async def test_list_sentiment_alerts_v2_status_filter(client, admin_headers):
    """GET /tenants/{tenantId}/sentiment/alerts?status=pending → 200（filter 傳遞正確）；無 DB 時接受 503。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/sentiment/alerts?status=pending",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body
        # 所有回傳 items 的 status 應為 pending
        for item in body["items"]:
            assert item["status"] == "pending"


@pytest.mark.asyncio
async def test_list_sentiment_alerts_v2_cross_tenant_403(client):
    """cross-tenant GET：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/sentiment/alerts",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_list_sentiment_alerts_v2_unauthenticated_401(client):
    """無 Authorization header → 401。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/sentiment/alerts",
    )
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# PATCH /tenants/{tenantId}/sentiment/alerts/{id} — update（帶 Idempotency-Key）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_sentiment_alert_v2_with_idempotency_key(client, admin_headers):
    """PATCH /tenants/{tenantId}/sentiment/alerts/{id} with Idempotency-Key → 200 或 404（無記錄）；無 DB 時接受 503。

    W1 教訓：寫操作測試必須帶 Idempotency-Key。
    """
    fake_alert_id = str(uuid.uuid4())
    headers = {
        **admin_headers,
        "Idempotency-Key": f"test-idem-{fake_alert_id}",
    }
    res = await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/sentiment/alerts/{fake_alert_id}",
        json={"status": "acknowledged"},
        headers=headers,
    )
    # 無真實 DB → 404 NOT_FOUND 或 503 DB_UNAVAILABLE；有 DB 但無此 alert → 404
    assert res.status_code in (200, 404, 503), res.text


@pytest.mark.asyncio
async def test_update_sentiment_alert_v2_cross_tenant_403(client):
    """cross-tenant PATCH：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_WRITE。

    cross-tenant guard 在 DB 查詢前執行 → 不依賴真實 DB。
    """
    fake_alert_id = str(uuid.uuid4())
    headers = {
        **_make_cross_tenant_headers(),
        "Idempotency-Key": f"test-idem-cross-{fake_alert_id}",
    }
    res = await client.patch(
        f"/tenants/{OTHER_TENANT_ID}/sentiment/alerts/{fake_alert_id}",
        json={"status": "acknowledged"},
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_update_sentiment_alert_v2_unauthenticated_401(client):
    """無 Authorization header PATCH → 401。"""
    fake_alert_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/sentiment/alerts/{fake_alert_id}",
        json={"status": "acknowledged"},
        headers={"Idempotency-Key": f"test-unauth-{fake_alert_id}"},
    )
    assert res.status_code == 401, res.text
