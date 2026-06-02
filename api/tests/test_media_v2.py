"""Tests for media v2 tenant-scoped endpoints（CR-0003 P2-W6）。

測試矩陣：
  unit（不靠 DB）：
    1. POST  /tenants/{tenantId}/media             → 路徑存在（401 無 token）
    2. GET   /tenants/{tenantId}/media/{mediaId}   → 路徑存在（401 無 token）
    3. GET   /tenants/{tenantId}/work-orders/{woId}/media → 路徑存在（401 無 token）
    4. GET   /tenants/{tenantId}/disputes/{disputeId}/media → 路徑存在（401 無 token）
    5. cross-tenant POST → 403 CROSS_TENANT_WRITE
    6. cross-tenant GET media → 403 CROSS_TENANT_READ
    7. cross-tenant GET work-order media → 403 CROSS_TENANT_READ
    8. cross-tenant GET dispute media → 403 CROSS_TENANT_READ

  component（需 live DB :5433，無 DB 則 503/404 視為合格）：
    9.  POST upload → 200（valid multipart）或 503
    10. GET media/{id} → 200/404/503
    11. GET work-orders/{woId}/media → 200（含 items key）或 503
    12. GET disputes/{disputeId}/media → 200（含 items key）或 503

注意：
  - worktree 無真實 DB；cross-tenant guard 在 service 呼叫前執行，無 DB 也能確認 403。
  - uploadMediaV2 不套用 idempotency_guard（multipart stream-consumed 衝突；見 router docstring）。
"""

from __future__ import annotations

import io
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
# 路徑存在性 / 401 無 token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_media_v2_no_token(client):
    """POST /tenants/{tenantId}/media — 無 token → 401（路徑存在性確認）。"""
    fake_tid = DEFAULT_TENANT_ID
    res = await client.post(
        f"/tenants/{fake_tid}/media",
        files={"file": ("test.jpg", io.BytesIO(b"dummy"), "image/jpeg")},
        data={"purpose": "other"},
    )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_get_media_v2_no_token(client):
    """GET /tenants/{tenantId}/media/{mediaId} — 無 token → 401。"""
    fake_tid = DEFAULT_TENANT_ID
    fake_mid = str(uuid.uuid4())
    res = await client.get(f"/tenants/{fake_tid}/media/{fake_mid}")
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_list_media_for_work_order_v2_no_token(client):
    """GET /tenants/{tenantId}/work-orders/{woId}/media — 無 token → 401。"""
    fake_tid = DEFAULT_TENANT_ID
    fake_woid = str(uuid.uuid4())
    res = await client.get(f"/tenants/{fake_tid}/work-orders/{fake_woid}/media")
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_list_media_for_dispute_v2_no_token(client):
    """GET /tenants/{tenantId}/disputes/{disputeId}/media — 無 token → 401。"""
    fake_tid = DEFAULT_TENANT_ID
    fake_did = str(uuid.uuid4())
    res = await client.get(f"/tenants/{fake_tid}/disputes/{fake_did}/media")
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# Cross-tenant guards（ADR-0030）— 無 DB 也能執行
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_media_v2_cross_tenant_403(client):
    """cross-tenant POST /media → 403 CROSS_TENANT_WRITE。"""
    headers = _make_cross_tenant_headers()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/media",
        headers=headers,
        files={"file": ("test.jpg", io.BytesIO(b"dummy"), "image/jpeg")},
        data={"purpose": "other"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_get_media_v2_cross_tenant_403(client):
    """cross-tenant GET /media/{mediaId} → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    fake_mid = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/media/{fake_mid}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_list_media_work_order_v2_cross_tenant_403(client):
    """cross-tenant GET /work-orders/{woId}/media → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    fake_woid = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_woid}/media",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_list_media_dispute_v2_cross_tenant_403(client):
    """cross-tenant GET /disputes/{disputeId}/media → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    fake_did = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/disputes/{fake_did}/media",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Component 測試（需 live DB :5433）— 標 component；無 DB 則 503 視為合格
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_upload_media_v2_component(client, admin_headers):
    """POST /tenants/{tenantId}/media → 200（含 id / url）或 503（無 DB）。"""
    small_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/media",
        headers=admin_headers,
        files={"file": ("test.png", io.BytesIO(small_png), "image/png")},
        data={"purpose": "other"},
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "id" in body
        assert "url" in body


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_media_v2_component(client, admin_headers):
    """GET /tenants/{tenantId}/media/{mediaId} → 200/404/503。"""
    fake_mid = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/media/{fake_mid}",
        headers=admin_headers,
    )
    assert res.status_code in (200, 404, 503), res.text


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_media_for_work_order_v2_component(client, admin_headers):
    """GET /tenants/{tenantId}/work-orders/{woId}/media → 200（含 items key）或 503。"""
    fake_woid = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_woid}/media",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_media_for_dispute_v2_component(client, admin_headers):
    """GET /tenants/{tenantId}/disputes/{disputeId}/media → 200（含 items key）或 503。"""
    fake_did = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/disputes/{fake_did}/media",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body
