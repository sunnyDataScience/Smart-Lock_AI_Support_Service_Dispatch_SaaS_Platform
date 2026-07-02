"""admin 視角技師月排班端點（getTechnicianScheduleV2，CIA-additive 2026-07-02）。

背景：後台技師詳情頁「本週排班」原為 hardcoded mock（固定 2026/04/20-26），
新增唯讀端點讓前端接真資料（工單數 keyed by technician_id + 休假/備勤）。
"""

from __future__ import annotations

import pytest

TENANT = "00000000-0000-0000-0000-000000000001"
DEMO_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"


@pytest.mark.component
@pytest.mark.asyncio
async def test_schedule_200_shape(client, admin_headers):
    r = await client.get(
        f"/tenants/{TENANT}/technicians/{DEMO_TECH}/schedule",
        params={"month": "2026-07"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["month"] == "2026-07"
    assert isinstance(body["work_orders_per_day"], dict)
    assert isinstance(body["leave_days"], list)
    assert isinstance(body["standby_days"], list)


@pytest.mark.component
@pytest.mark.asyncio
async def test_schedule_unknown_tech_404(client, admin_headers):
    r = await client.get(
        f"/tenants/{TENANT}/technicians/00000000-0000-0000-0000-0000000000ff/schedule",
        params={"month": "2026-07"},
        headers=admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.component
@pytest.mark.asyncio
async def test_schedule_missing_month_422(client, admin_headers):
    r = await client.get(
        f"/tenants/{TENANT}/technicians/{DEMO_TECH}/schedule",
        headers=admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_schedule_cross_tenant_403(client, admin_headers):
    other = "00000000-0000-0000-0000-000000000002"
    r = await client.get(
        f"/tenants/{other}/technicians/{DEMO_TECH}/schedule",
        params={"month": "2026-07"},
        headers=admin_headers,
    )
    assert r.status_code == 403
