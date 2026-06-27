"""CR-0107 師傅獎懲明細端點測試。

  C-1  POST 手動獎金/扣款 → 201 + 列表含
  C-2  DELETE 手動 → 移除
  C-3  自動帶入取消失約扣款（cancellation.technician_penalty）→ 列表含、source=cancellation、不可刪
  C-4  非法 entry_type → 422
  C-5  cross-tenant → 403
"""

from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


async def _create_technician(client, admin_headers) -> str:
    idem = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"display_name": f"pb-test-{idem[:8]}", "coverage_areas": ["taipei"]},
        headers={**admin_headers, "Idempotency-Key": idem},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _add_cancellation_penalty(tech_id: str, amount: float) -> tuple[str, str]:
    """插一張該技師的工單 + 一筆取消罰，回 (wo_id, cancellation_id)。"""
    import core.db as db_module

    wo_id = str(uuid.uuid4())
    cxl_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, tenant_id, technician_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
        (wo_id, DEFAULT_TENANT_ID, tech_id),
    )
    await db_module._conn.execute(
        "INSERT INTO cancellation (id, tenant_id, work_order_id, cancellation_stage, "
        "  initiator_role, reason_code, technician_penalty, audit_event_id, config_version_used) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'S3', 'technician', 'no_show', %s, %s::uuid, 'v1')",
        (cxl_id, DEFAULT_TENANT_ID, wo_id, amount, str(uuid.uuid4())),
    )
    return wo_id, cxl_id


async def _cleanup(tech_id: str, wo_ids: list[str]) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    for wo in wo_ids:
        await db_module._conn.execute("DELETE FROM cancellation WHERE work_order_id = %s::uuid", (wo,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo,))
    await db_module._conn.execute(
        "DELETE FROM saas.technician_penalty_bonus_ledger WHERE technician_id = %s::uuid", (tech_id,))
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id = %s::uuid", (tech_id,))
    row = await cur.fetchone()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute("DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    if row and row[0]:
        await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (row[0],))


def _path(tech_id: str, entry_id: str | None = None) -> str:
    base = f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}/penalty-bonus"
    return f"{base}/{entry_id}" if entry_id else base


@pytest.mark.asyncio
@pytest.mark.component
async def test_manual_create_list_delete(client, admin_headers):
    """C-1/C-2：手動登錄獎金 → 列表含 → 刪除。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.post(
            _path(tech_id),
            json={"entry_type": "bonus", "title": "高評價獎金", "amount": 200,
                  "occurred_date": date.today().isoformat()},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201, res.text
        entry = res.json()["data"]
        assert entry["entry_type"] == "bonus" and entry["amount"] == 200.0
        assert entry["source"] == "manual" and entry["editable"] is True
        eid = entry["id"]

        lst = await client.get(_path(tech_id), headers=admin_headers)
        assert any(e["id"] == eid for e in lst.json()["data"])

        dele = await client.delete(_path(tech_id, eid), headers=admin_headers)
        assert dele.status_code == 200, dele.text
        lst2 = await client.get(_path(tech_id), headers=admin_headers)
        assert all(e["id"] != eid for e in lst2.json()["data"])
    finally:
        await _cleanup(tech_id, [])


@pytest.mark.asyncio
@pytest.mark.component
async def test_auto_cancellation_penalty_listed_readonly(client, admin_headers):
    """C-3：取消失約扣款自動帶入、source=cancellation、不可刪（422）。"""
    tech_id = await _create_technician(client, admin_headers)
    wo, _cxl = await _add_cancellation_penalty(tech_id, 500.0)
    try:
        lst = await client.get(_path(tech_id), headers=admin_headers)
        autos = [e for e in lst.json()["data"] if e["source"] == "cancellation"]
        assert len(autos) == 1
        a = autos[0]
        assert a["entry_type"] == "penalty" and a["amount"] == 500.0
        assert a["editable"] is False and a["id"].startswith("cancel:")

        # 不可刪自動帶入
        dele = await client.delete(_path(tech_id, a["id"]), headers=admin_headers)
        assert dele.status_code == 422, dele.text
    finally:
        await _cleanup(tech_id, [wo])


@pytest.mark.asyncio
@pytest.mark.component
async def test_invalid_entry_type_422(client, admin_headers):
    """C-4：非法 entry_type → 422。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.post(
            _path(tech_id),
            json={"entry_type": "invalid", "title": "x", "amount": 1,
                  "occurred_date": date.today().isoformat()},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 422, res.text
    finally:
        await _cleanup(tech_id, [])


@pytest.mark.asyncio
@pytest.mark.component
async def test_cross_tenant_403(client, admin_headers):
    """C-5：cross-tenant → 403。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.get(
            f"/tenants/{OTHER_TENANT_ID}/technicians/{tech_id}/penalty-bonus",
            headers=admin_headers,
        )
        assert res.status_code == 403, res.text
    finally:
        await _cleanup(tech_id, [])
