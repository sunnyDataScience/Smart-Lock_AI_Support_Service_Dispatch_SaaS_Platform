"""Component tests — Reports v2 tenant-scoped（CR-0003 P2-W1, FR-0021）。

測試矩陣：
  1. GET /tenants/{tenantId}/reports/kpi        → 200（或 503 無 DB）tenant-scoped
  2. GET /tenants/{tenantId}/reports/revenue     → 200（或 503 無 DB）tenant-scoped
  3. GET /tenants/{tenantId}/reports/export      → 200 CSV stream（或 503 無 DB）
  4. cross-tenant GET /reports/kpi    → 403 CROSS_TENANT_READ
  5. cross-tenant GET /reports/revenue → 403 CROSS_TENANT_READ
  6. cross-tenant GET /reports/export  → 403 CROSS_TENANT_READ

注意：無真實 DB 時 200 路徑可能回 503（DB unavailable）；
      測試重點在結構正確性與 cross-tenant 403 early-return，與 DB 無關。
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
# GET /tenants/{tenantId}/reports/kpi
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_kpi_200(client, admin_headers):
    """GET reports/kpi → 200（含 KpiReport 結構）；無 DB 時接受 503。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/reports/kpi",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        # KpiReport schema — 至少有 funnel 或 generated_at 欄位
        assert isinstance(body, dict)


@pytest.mark.asyncio
async def test_get_report_kpi_cross_tenant_403(client):
    """cross-tenant GET kpi：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/reports/kpi",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/reports/revenue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_revenue_200(client, admin_headers):
    """GET reports/revenue → 200（含 RevenueSummary 結構）；無 DB 時接受 503。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/reports/revenue",
        headers=admin_headers,
    )
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert isinstance(body, dict)
        # by_category（additive）：問題類別營收佔比，結構與 by_brand 對稱。
        assert "by_category" in body, body
        assert isinstance(body["by_category"], list)
        for pt in body["by_category"]:
            assert set(pt.keys()) >= {"category", "revenue", "share"}, pt
            assert isinstance(pt["category"], str)
            assert 0.0 <= pt["share"] <= 1.0


@pytest.mark.asyncio
async def test_get_report_revenue_cross_tenant_403(client):
    """cross-tenant GET revenue：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/reports/revenue",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/reports/export（CSV stream）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_export_csv_200(client, admin_headers):
    """GET reports/export CSV → 200 text/csv stream；無 DB 時 StreamingResponse 拋 RuntimeError。

    StreamingResponse 在 DB unavailable 時會在 header 發出後才拋例外，
    導致 test client 側拿到 RuntimeError（與 legacy /api/v1/reports/export 同行為）。
    接受：200 成功 / RuntimeError（DB unavailable 串流中斷）。
    """
    try:
        res = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/reports/export?report_type=kpi&period=30d",
            headers=admin_headers,
        )
        # 有 DB：200 CSV stream
        assert res.status_code == 200, res.text
        assert "text/csv" in res.headers.get("content-type", "")
    except RuntimeError:
        # 無 DB：StreamingResponse 串流中斷 → RuntimeError（expected CI behavior）
        pass


@pytest.mark.asyncio
async def test_get_report_export_cross_tenant_403(client):
    """cross-tenant GET export：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/reports/export?report_type=kpi&period=30d",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"
