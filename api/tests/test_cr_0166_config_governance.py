"""CR-0166 R1：M18 config 治理——SoD header UUID/存在性、受保護層、owner_role_codes。"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.component

TENANT_ID = "00000000-0000-0000-0000-000000000001"
INITIATOR_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"  # admin（seed）
APPROVER_ID = "11111111-1111-1111-1111-111111111111"   # operations_manager（seed）


def _draft_headers(admin_headers, initiator=INITIATOR_ID):
    return {**admin_headers, "X-Initiator": initiator, "Idempotency-Key": str(uuid.uuid4())}


# ── R1-2：SoD header UUID + 存在性 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_draft_non_uuid_initiator_422(client, admin_headers):
    """X-Initiator 非 UUID → 422（原會在 ::uuid cast 爆 500）。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/sla_policy/dispatch_sla",
        headers=_draft_headers(admin_headers, initiator="not-a-uuid"),
        json={"proposed_value": {"minutes": 30}, "reason": "test"},
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_draft_nonexistent_initiator_422(client, admin_headers):
    """X-Initiator 格式合法但不存在於 users → 422 INITIATOR_NOT_FOUND（審計斷鏈防護）。"""
    ghost = str(uuid.uuid4())
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/tax_policy/rate",
        headers=_draft_headers(admin_headers, initiator=ghost),
        json={"proposed_value": {"rate": 5}, "reason": "test"},
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "INITIATOR_NOT_FOUND"


# ── R1-6：受保護層 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_protected_namespace_tenant_override_blocked(client, admin_headers):
    """payment_gate 為受保護 namespace → 租戶層 draft 被擋 403 CONFIG_PROTECTED_OVERRIDE。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/payment_gate/enabled",
        headers=_draft_headers(admin_headers),
        json={"proposed_value": {"enabled": True}, "reason": "test"},
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "CONFIG_PROTECTED_OVERRIDE"


# ── R1-7：owner_role_codes 動態縮權 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_owner_role_dispatcher_blocked(client, dispatcher_headers):
    """tax_policy owner=operations_manager；dispatcher（在 OPS_ROLES 外）→ 403。

    注意：dispatcher 不在 OPS_ROLES，會先被 router 靜態 gate 擋（403），
    這正是「無權者進不來」的期望行為。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/tax_policy/rate",
        headers={**dispatcher_headers, "X-Initiator": INITIATOR_ID,
                 "Idempotency-Key": str(uuid.uuid4())},
        json={"proposed_value": {"rate": 5}, "reason": "test"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_owner_role_ops_manager_allowed(client, secondary_admin_headers):
    """tax_policy owner=operations_manager；ops manager 可建 draft（動態縮權放行）。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/tax_policy/rate",
        headers={**secondary_admin_headers, "X-Initiator": APPROVER_ID,
                 "Idempotency-Key": str(uuid.uuid4())},
        json={"proposed_value": {"rate": 5}, "reason": "test"},
    )
    assert res.status_code == 201, res.text


@pytest.mark.asyncio
async def test_admin_bypasses_owner_role(client, admin_headers):
    """admin 永遠可寫 owner 受限 namespace（全權治理角色 bypass）。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/tax_policy/rate",
        headers=_draft_headers(admin_headers),
        json={"proposed_value": {"rate": 7}, "reason": "admin override"},
    )
    assert res.status_code == 201, res.text
