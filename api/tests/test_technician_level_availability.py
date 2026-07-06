"""CR-0104 等級 + 在線狀態真接線測試。

驗證 get_technician 不再回硬補常數，而是讀真實欄位：
  - availability ← technicians.online_state（取代 _DEFAULT_AVAILABILITY）
  - level        ← technicians.level（migration 080，取代 _DEFAULT_LEVEL）

CR-0114 收斂：品牌端 PATCH updateTechnicianV2 已廢止（師傅主檔歸平台方,
契約回歸守衛見 test_technicians_v2_endpoint.test_brand_update_technician_endpoint_removed）
→ 原「PATCH 指派 level」測試改為直寫 DB 驗證 GET 讀真值;測資建立由原品牌端
POST createTechnician（同輪廢止）改為直插 technicians 列。
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
    """直插一列最小 technicians（不建 users;本檔測試只做 GET 讀取）。"""
    import core.db as db_module

    assert await db_module._ensure_conn()
    tech_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, name, phone, capabilities, service_regions, status) "
        "VALUES (%s::uuid, %s::uuid, %s, '0900000000', '[]'::jsonb, '[\"taipei\"]'::jsonb, 'active')",
        (tech_id, DEFAULT_TENANT_ID, f"lvl-test-{tech_id[:8]}"),
    )
    return tech_id


async def _cleanup_technician(tech_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))


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
async def test_level_reads_real_column(client, admin_headers):
    """改 DB level='A' → GET 回 'A'（讀 technicians.level 真值,非硬補常數）。"""
    import core.db as db_module

    tech_id = await _create_technician(client, admin_headers)
    try:
        await db_module._conn.execute(
            "UPDATE technicians SET level='A' WHERE id=%s::uuid", (tech_id,))
        res = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}", headers=admin_headers)
        assert res.json()["data"]["level"] == "A"
    finally:
        await _cleanup_technician(tech_id)
