"""Component tests for Dashboard v2 tenant-scoped endpoint（CR-0003 P2-W1 / FR-0021）。

測試矩陣：
  1. GET /tenants/{tenantId}/dashboard/stats → 200 tenant-scoped stats（period=7d 預設）
  2. GET /tenants/{tenantId}/dashboard/stats?period=today → 200 period 切換
  3. cross-tenant guard → 403 CROSS_TENANT_READ
  4. 未認證 → 401

注意：worktree 無真實 DB，component mark 測試在主 worktree 含 DB 的環境跑。
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
    token_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=token_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# 200 — tenant-scoped dashboard stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_stats_v2_200_default_period(client, admin_headers):
    """GET /tenants/{tenantId}/dashboard/stats → 200（period 預設 7d）。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dashboard/stats",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # 驗 required fields（DashboardStats schema）
    assert "period" in body
    assert "conversations" in body
    assert "resolution" in body
    conv = body["conversations"]
    assert "total" in conv
    assert "active" in conv
    assert "resolved" in conv
    assert "escalated" in conv


@pytest.mark.asyncio
async def test_get_dashboard_stats_v2_200_period_today(client, admin_headers):
    """GET /tenants/{tenantId}/dashboard/stats?period=today → 200 period=today。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dashboard/stats?period=today",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"] == "today"


@pytest.mark.asyncio
async def test_get_dashboard_stats_v2_200_period_30d(client, admin_headers):
    """GET /tenants/{tenantId}/dashboard/stats?period=30d → 200 period=30d。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dashboard/stats?period=30d",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"] == "30d"


# ---------------------------------------------------------------------------
# 403 — cross-tenant guard（ADR-0030）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_stats_v2_cross_tenant_403(client):
    """JWT tenant = DEFAULT 但 path = OTHER_TENANT → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/dashboard/stats",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# 401 — 未認證
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_stats_v2_unauthenticated_401(client):
    """無 Authorization header → 401。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dashboard/stats",
    )
    assert res.status_code == 401, res.text
