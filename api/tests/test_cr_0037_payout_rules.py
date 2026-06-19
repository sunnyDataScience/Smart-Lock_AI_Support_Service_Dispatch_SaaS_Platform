"""CR-0037 師傅拆帳規則主檔 測試（component，需 migration 045）。

- seed 69 筆可讀；get_rule(service×level) 取值
- compute_payout 純計算（夜間/急件加成疊乘）
- API RBAC：base_payout 僅後台管理角色可見（customer_service 遮蔽）
"""

from __future__ import annotations

import pytest

import core.db as db_module
from services import payout_rule_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_payout_rules_seeded(client):
    assert await db_module._ensure_conn()
    rules = await payout_rule_service.list_rules(tenant_id=DEFAULT_TENANT_ID, include_cost=True)
    assert len(rules) == 69  # 23 服務 × A/B/C（全域 tenant_id NULL）
    # 含 base_payout（include_cost=True）
    assert "base_payout" in rules[0]


@pytest.mark.asyncio
async def test_payout_rule_get(client):
    assert await db_module._ensure_conn()
    # include_cost=True 才回 base_payout_raw（內部成本）
    r = await payout_rule_service.get_rule(
        tenant_id=DEFAULT_TENANT_ID, service_code="SVC-RES-001", level_id="LV-A", include_cost=True)
    assert r is not None
    assert r["base_payout_raw"] == 150.0  # sheet 21 到府檢測 LV-A 基礎拆帳
    assert r["night_surcharge_pct"] == 0.2 and r["urgent_surcharge_pct"] == 0.15
    # include_cost 預設 False → 不露 base_payout
    masked = await payout_rule_service.get_rule(
        tenant_id=DEFAULT_TENANT_ID, service_code="SVC-RES-001", level_id="LV-A")
    assert "base_payout" not in masked and "base_payout_raw" not in masked
    # 不存在組合 → None
    assert await payout_rule_service.get_rule(
        tenant_id=DEFAULT_TENANT_ID, service_code="SVC-NOPE", level_id="LV-A") is None


def test_compute_payout_pure():
    """純計算：base × (1+夜間) × (1+急件)。"""
    # base 100，無加成
    assert payout_rule_service.compute_payout(base_payout=100) == 100.0
    # 夜間 0.2：100 × 1.2 = 120
    assert payout_rule_service.compute_payout(base_payout=100, night=True, night_pct=0.2) == 120.0
    # 夜間 0.2 + 急件 0.15：100 × 1.2 × 1.15 = 138
    assert payout_rule_service.compute_payout(
        base_payout=100, night=True, urgent=True, night_pct=0.2, urgent_pct=0.15) == 138.0


@pytest.mark.asyncio
async def test_payout_rules_rbac_masking(client, admin_headers, customer_service_headers):
    """API：admin 見 base_payout、customer_service 遮蔽。"""
    path = f"/tenants/{DEFAULT_TENANT_ID}/payout-rules?service_code=SVC-RES-001"
    admin_res = await client.get(path, headers=admin_headers)
    assert admin_res.status_code == 200, admin_res.text
    admin_body = admin_res.json()
    assert admin_body["cost_visible"] is True
    assert "base_payout" in admin_body["data"][0]

    cs_res = await client.get(path, headers=customer_service_headers)
    assert cs_res.status_code == 200, cs_res.text
    cs_body = cs_res.json()
    assert cs_body["cost_visible"] is False
    assert "base_payout" not in cs_body["data"][0]  # 結構性遮蔽
    assert "base_payout" not in str(cs_body)  # 不洩漏拆帳成本
