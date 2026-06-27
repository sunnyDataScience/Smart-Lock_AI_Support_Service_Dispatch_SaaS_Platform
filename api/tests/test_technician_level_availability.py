"""CR-0104 等級 + 在線狀態真接線測試。

驗證 get_technician 不再回硬補常數，而是讀真實欄位：
  - availability ← technicians.online_state（取代 _DEFAULT_AVAILABILITY）
  - level        ← technicians.level（migration 080，取代 _DEFAULT_LEVEL）
並驗證 PATCH 可手動指派 level（業主裁決「後台手動指派」）。
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID


async def _create_technician(client, admin_headers) -> str:
    idem = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"display_name": f"lvl-test-{idem[:8]}", "coverage_areas": ["taipei"]},
        headers={**admin_headers, "Idempotency-Key": idem},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _cleanup_technician(tech_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id = %s::uuid", (tech_id,))
    row = await cur.fetchone()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    if row and row[0]:
        await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (row[0],))


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_returns_real_defaults(client, admin_headers):
    """新建技師：availability 預設 'available'（online_state DEFAULT）、level 預設 'C'（migration 080 DEFAULT）。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}", headers=admin_headers)
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["availability"] == "available"
        assert data["level"] == "C"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_availability_reads_real_online_state(client, admin_headers):
    """改 DB online_state='busy' → GET availability 回真值 'busy'（非硬補常數）。"""
    import core.db as db_module

    tech_id = await _create_technician(client, admin_headers)
    try:
        await db_module._conn.execute(
            "UPDATE technicians SET online_state='busy' WHERE id=%s::uuid", (tech_id,))
        res = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}", headers=admin_headers)
        assert res.json()["data"]["availability"] == "busy"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_patch_assigns_level(client, admin_headers):
    """PATCH level='A' → GET 回 'A'（手動指派落庫）。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        patch = await client.patch(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}",
            json={"level": "A"},
            headers=admin_headers,
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["data"]["level"] == "A"

        res = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}", headers=admin_headers)
        assert res.json()["data"]["level"] == "A"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_patch_invalid_level_422(client, admin_headers):
    """PATCH level='Z'（非 S/A/B/C）→ 422（TechnicianLevel enum 守門）。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        patch = await client.patch(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}",
            json={"level": "Z"},
            headers=admin_headers,
        )
        assert patch.status_code == 422, patch.text
    finally:
        await _cleanup_technician(tech_id)
