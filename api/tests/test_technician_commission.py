"""CR-0106 師傅佣金月結（固定工資制）端點測試。

驗證引擎：completed work_orders × quote_line_items(service_code) × payout_rule(service_code, level)
  C-1  有完工單 + 服務明細 → gross = base_payout × qty
  C-2  無完工單 → gross 0、empty lines
  C-3  service_code 無對應費率 → line mapped=false、payout 0、計入 unmapped
  C-4  等級映射：level B → LV-B 費率
  C-5  cross-tenant → 403
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


async def _create_technician(client, admin_headers, level: str = "B") -> str:
    idem = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"display_name": f"comm-test-{idem[:8]}", "coverage_areas": ["taipei"]},
        headers={**admin_headers, "Idempotency-Key": idem},
    )
    assert res.status_code == 201, res.text
    tech_id = res.json()["data"]["id"]
    await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}",
        json={"level": level},
        headers=admin_headers,
    )
    return tech_id


async def _add_completed_wo(tech_id: str, service_code: str | None, qty: int) -> str:
    """直接插一張本月完工工單 + 一筆服務明細，回 work_order_id。"""
    import core.db as db_module

    wo_id = str(uuid.uuid4())
    # 本月中間的時間戳（確保落在當月區間）
    today = date.today()
    completed = datetime(today.year, today.month, 15, 10, 0, tzinfo=timezone.utc)
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, tenant_id, technician_id, completion_status, completed_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'closed', %s)",
        (wo_id, DEFAULT_TENANT_ID, tech_id, completed),
    )
    await db_module._conn.execute(
        "INSERT INTO quote_line_items (work_order_id, tenant_id, item_name, category, "
        "  quantity, unit_price, customer_price, service_code) "
        "VALUES (%s::uuid, %s::uuid, %s, 'service', %s, 0, 0, %s)",
        (wo_id, DEFAULT_TENANT_ID, "服務項目", qty, service_code),
    )
    return wo_id


async def _cleanup(tech_id: str, wo_ids: list[str]) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    for wo in wo_ids:
        await db_module._conn.execute(
            "DELETE FROM quote_line_items WHERE work_order_id = %s::uuid", (wo,))
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE id = %s::uuid", (wo,))
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id = %s::uuid", (tech_id,))
    row = await cur.fetchone()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    if row and row[0]:
        await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (row[0],))


def _path(tech_id: str) -> str:
    return f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}/commission-summary"


@pytest.mark.asyncio
@pytest.mark.component
async def test_commission_computes_gross_from_payout_rule(client, admin_headers):
    """C-1/C-4：level B 技師，完工單含 SVC-ELK-001 ×2 → gross = 500×2 = 1000。"""
    tech_id = await _create_technician(client, admin_headers, level="B")
    wo = await _add_completed_wo(tech_id, "SVC-ELK-001", 2)
    try:
        res = await client.get(_path(tech_id), headers=admin_headers)
        assert res.status_code == 200, res.text
        d = res.json()["data"]
        assert d["level"] == "B" and d["level_id"] == "LV-B"
        assert d["completed_orders"] == 1
        assert d["gross_amount"] == 1000.0, d
        assert d["net_amount"] == 1000.0  # 扣項暫 0
        assert len(d["lines"]) == 1
        ln = d["lines"][0]
        assert ln["service_code"] == "SVC-ELK-001"
        assert ln["mapped"] is True
        assert ln["unit_payout"] == 500.0 and ln["line_total"] == 1000.0
    finally:
        await _cleanup(tech_id, [wo])


@pytest.mark.asyncio
@pytest.mark.component
async def test_commission_empty_when_no_completed_orders(client, admin_headers):
    """C-2：無完工單 → gross 0、lines 空。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.get(_path(tech_id), headers=admin_headers)
        assert res.status_code == 200, res.text
        d = res.json()["data"]
        assert d["completed_orders"] == 0
        assert d["gross_amount"] == 0.0
        assert d["lines"] == []
    finally:
        await _cleanup(tech_id, [])


@pytest.mark.asyncio
@pytest.mark.component
async def test_commission_unmapped_service_code(client, admin_headers):
    """C-3：service_code 無對應費率 → mapped=false、payout 0、unmapped 計數。"""
    tech_id = await _create_technician(client, admin_headers, level="B")
    wo = await _add_completed_wo(tech_id, "SVC-NONEXISTENT-999", 3)
    try:
        res = await client.get(_path(tech_id), headers=admin_headers)
        d = res.json()["data"]
        assert d["gross_amount"] == 0.0
        assert d["unmapped_count"] == 1
        assert d["lines"][0]["mapped"] is False
    finally:
        await _cleanup(tech_id, [wo])


@pytest.mark.asyncio
@pytest.mark.component
async def test_commission_cross_tenant_403(client, admin_headers):
    """C-5：cross-tenant → 403。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.get(
            f"/tenants/{OTHER_TENANT_ID}/technicians/{tech_id}/commission-summary",
            headers=admin_headers,
        )
        assert res.status_code == 403, res.text
    finally:
        await _cleanup(tech_id, [])
