"""GET /api/v1/reports/export component tests。

涵蓋：
  - exportReport KPI CSV → 200 + content-type csv + 包含 funnel / dispute_rates 段落
  - exportReport revenue CSV → 200 + 包含 trend / by_brand 段落
  - exportReport technician_ranking CSV → 200 stub csv
  - exportReport PDF → 422（尚未實作）
  - exportReport 不合法 report_type → 422
  - exportReport 無 token → 401
  - exportReport reviewer 角色 → 403
  - exportReport 不合法 period → 422
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_export_kpi_csv_success(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=kpi&format=csv&period=30d",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert "text/csv" in res.headers.get("content-type", "")
    body = res.text
    assert "funnel" in body
    assert "dispute_rates" in body


@pytest.mark.asyncio
async def test_export_revenue_csv_success(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=revenue&format=csv",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.text
    assert "kpis" in body
    assert "trend" in body
    assert "by_brand" in body


@pytest.mark.asyncio
async def test_export_technician_ranking_csv_stub(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=technician_ranking&format=csv",
        headers=admin_headers,
    )
    assert res.status_code == 200
    body = res.text
    assert "technician_id" in body  # header line
    assert "completed_orders" in body


@pytest.mark.asyncio
async def test_export_pdf_returns_422_pending_impl(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=kpi&format=pdf",
        headers=admin_headers,
    )
    assert res.status_code == 422
    assert "PDF" in res.text or "pdf" in res.text.lower()


@pytest.mark.asyncio
async def test_export_invalid_report_type_returns_422(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=cosmic_rays&format=csv",
        headers=admin_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_export_unauthenticated_returns_401(client):
    res = await client.get(
        "/api/v1/reports/export?report_type=kpi&format=csv"
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_export_reviewer_role_returns_403(client):
    """reviewer 不在白名單；應拿到 403。"""
    from tests.conftest import DEFAULT_TENANT_ID, _make_token

    token = _make_token(
        user_id="33333333-3333-3333-3333-333333333333", role="reviewer"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }
    res = await client.get(
        "/api/v1/reports/export?report_type=kpi&format=csv", headers=headers
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_export_invalid_period_returns_422(client, admin_headers):
    res = await client.get(
        "/api/v1/reports/export?report_type=kpi&format=csv&period=99y",
        headers=admin_headers,
    )
    assert res.status_code == 422
