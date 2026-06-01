"""Cancellation 6-stage 端點整合測試（需 live DB）。

對齊 spec: POST /tenants/{tenantId}/work-orders/{woId}/cancel（ADR-0102 / AC-V11-08）。
驗證：tenant-scoped path + SoD headers + 6 階段費用 + 409 terminal + 403 SoD。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def make_wo(client):
    """工廠：建 conv→pc→wo chain（tenant=admin），回 wo_id。可指定初始 status。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"wo": [], "pc": [], "conv": []}

    async def _factory(*, status: str = "assigned", estimated_price: float = 2000.0) -> str:
        await _ensure_conn()
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"cnl-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model) "
            "VALUES (%s::uuid, %s::uuid, 'Test', 'TestModel')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, priority, estimated_price) "
            "VALUES (%s::uuid, %s::uuid, %s, '台北市中正區test', 'normal', %s)",
            (wo_id, pc_id, status, estimated_price),
        )
        created["wo"].append(wo_id)
        return wo_id

    yield _factory

    import core.db as db_module
    for wo in created["wo"]:
        await db_module._conn.execute("DELETE FROM cancellation WHERE work_order_id = %s::uuid", (wo,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo,))
    for pc in created["pc"]:
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc,))
    for conv in created["conv"]:
        await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (conv,))


def _path(wo_id: str) -> str:
    return f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{wo_id}/cancel"


def _sod_headers(admin_headers: dict, *, initiator="csm-1", approver="sup-1", executor=None) -> dict:
    h = dict(admin_headers)
    h["Idempotency-Key"] = str(uuid.uuid4())
    h["X-Initiator"] = initiator
    h["X-Approver"] = approver
    if executor:
        h["X-Executor"] = executor
    return h


@pytest.mark.asyncio
async def test_cancel_s2_dispatched_not_departed_charges_300(make_wo, client, admin_headers):
    wo_id = await make_wo(status="assigned")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "dispatched_not_departed", "initiator_role": "customer"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["cancellation_stage"] == "S2"
    assert data["customer_fee"] == 300.0
    assert data["travel_fee"] == 0.0
    assert data["audit_event_id"]


@pytest.mark.asyncio
async def test_cancel_s1_quote_not_confirmed_is_free(make_wo, client, admin_headers):
    wo_id = await make_wo(status="created")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "quote_not_confirmed", "initiator_role": "customer"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["cancellation_stage"] == "S1"
    assert data["customer_fee"] == 0.0


@pytest.mark.asyncio
async def test_cancel_goodwill_waiver_zeros_fee(make_wo, client, admin_headers):
    wo_id = await make_wo(status="assigned")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "dispatched_not_departed", "initiator_role": "customer", "goodwill_waiver": True},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["customer_fee"] == 0.0


@pytest.mark.asyncio
async def test_cancel_sod_violation_same_initiator_approver_403(make_wo, client, admin_headers):
    wo_id = await make_wo(status="assigned")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers, initiator="same-user", approver="same-user"),
        json={"reason_code": "dispatched_not_departed", "initiator_role": "customer"},
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "SOD_VIOLATION"


@pytest.mark.asyncio
async def test_cancel_unknown_reason_code_422(make_wo, client, admin_headers):
    wo_id = await make_wo(status="assigned")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "totally_bogus", "initiator_role": "customer"},
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "REASON_CODE_UNKNOWN"


@pytest.mark.asyncio
async def test_cancel_evidence_missing_422(make_wo, client, admin_headers):
    wo_id = await make_wo(status="accepted")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "customer_not_onsite", "initiator_role": "customer"},
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "EVIDENCE_MISSING"


@pytest.mark.asyncio
async def test_cancel_terminal_state_409(make_wo, client, admin_headers):
    wo_id = await make_wo(status="completed")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "dispatched_not_departed", "initiator_role": "customer"},
    )
    assert res.status_code == 409
    assert res.json()["error_code"] == "WO_STATE_INVALID"


@pytest.mark.asyncio
async def test_cancel_persists_config_version_and_stage(make_wo, client, admin_headers):
    wo_id = await make_wo(status="accepted")
    res = await client.post(
        _path(wo_id),
        headers=_sod_headers(admin_headers),
        json={"reason_code": "en_route_cancelled", "initiator_role": "customer", "distance_km": 5},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["cancellation_stage"] == "S3"
    assert data["customer_fee"] == 300.0
    assert data["travel_fee"] == 600.0  # min 500 + 20*5

    import core.db as db_module
    cur = await db_module._conn.execute(
        "SELECT config_version_used, cancellation_stage FROM cancellation WHERE work_order_id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    assert row is not None
    assert row[0]  # config_version_used 有寫入
    assert row[1] == "S3"
