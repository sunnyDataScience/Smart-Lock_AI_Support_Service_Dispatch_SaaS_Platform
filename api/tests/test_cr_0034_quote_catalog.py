"""CR-0034 報價主檔測試（component，真 DB；migration 040 seed）。

- get_catalog 回 29 服務 + 20 材料 + 12 規則，全 is_mock
- include_cost=True 露 internal cost；False 遮蔽
- 取消費規則為「已知規格」(ADR-0102)，急件/夜間/假日為「待決策」
"""

from __future__ import annotations

import pytest

import core.db as db_module
from services import quote_catalog_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_catalog_seeded_and_mock(client):
    assert await db_module._ensure_conn()
    cat = await quote_catalog_service.get_catalog(
        tenant_id=DEFAULT_TENANT_ID, include_cost=True)
    assert len(cat["services"]) >= 29
    assert len(cat["materials"]) >= 20
    assert len(cat["surcharges"]) >= 12
    # 全 mock
    assert all(s["is_mock"] for s in cat["services"])
    # 取消費已知規格（ADR-0102）；急件待決策
    rules = {r["rule_code"]: r for r in cat["surcharges"]}
    assert rules["CNL-S2"]["decision_status"] == "已知規格"
    assert rules["URG-01"]["decision_status"] == "待決策"


@pytest.mark.asyncio
async def test_internal_cost_rbac_mask(client):
    assert await db_module._ensure_conn()
    admin_view = await quote_catalog_service.get_catalog(
        tenant_id=DEFAULT_TENANT_ID, include_cost=True)
    cust_view = await quote_catalog_service.get_catalog(
        tenant_id=DEFAULT_TENANT_ID, include_cost=False)
    assert all("internal_base_cost" in s for s in admin_view["services"])
    assert all("internal_base_cost" not in s for s in cust_view["services"])
    # 對外價兩者都有
    assert all("suggested_customer_price" in s for s in cust_view["services"])
