"""Refund 三維 SoD + 5-tier 端點整合測試（需 live DB）。

對齊 spec: POST /tenants/{tenantId}/refunds（ADR-0040 v2 / BR-REFUND-006 / FR-0014）。
驗證：tenant-scoped path + SoD headers + 伺服器端 tier 推算 + 403 SoD + 422 refund_class。

⚠ 本檔為 @pytest.mark.component，需 live DB（dev 環境 lock_AI_data）+ migration 002
已套用（refund_requests.tier / refund_class / 三維欄位）。若 DB 不可用，這些測試會
在 fixture 階段 error/skip — 屬預期，unit 測試（test_refund_sod_5tier.py）已覆蓋核心規則。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def make_wo(client):
    """工廠：建 conv→pc→wo chain（tenant=admin），回 wo_id。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"wo": [], "pc": [], "conv": [], "refund": []}

    async def _factory(*, status: str = "completed", estimated_price: float = 8000.0) -> str:
        await _ensure_conn()
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"rfd-{conv_id[:8]}"),
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
        await db_module._conn.execute("DELETE FROM refund_requests WHERE work_order_id = %s::uuid", (wo,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo,))
    for pc in created["pc"]:
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc,))
    for conv in created["conv"]:
        await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (conv,))


def _path(tenant_id: str = DEFAULT_TENANT_ID) -> str:
    return f"/tenants/{tenant_id}/refunds"


# SoD 行為人 ID 為 UUID（對齊 migration 002 的 initiator_user_id/approver_user_ids/executor_user_id UUID 欄位）
_INITIATOR_UID = "a0000000-0000-4000-8000-000000000001"
_APPROVER_UID = "a0000000-0000-4000-8000-000000000002"
_EXECUTOR_UID = "a0000000-0000-4000-8000-000000000003"
_SAME_UID = "a0000000-0000-4000-8000-00000000000f"


def _sod_headers(admin_headers: dict, *, initiator=_INITIATOR_UID, approver=_APPROVER_UID, executor=None) -> dict:
    h = dict(admin_headers)
    h["Idempotency-Key"] = str(uuid.uuid4())
    h["X-Initiator"] = initiator
    h["X-Approver"] = approver
    if executor:
        h["X-Executor"] = executor
    return h


@pytest.mark.asyncio
async def test_create_refund_tier_resolved_l3(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={
            "work_order_id": wo_id,
            "amount": 8000,            # 5000 < 8000 <= 30000 → L3
            "refund_class": "product",
            "reason": "客戶退貨",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["tier"] == "L3"
    assert data["refund_class"] == "product"
    assert data["state"] == "pending"
    assert data["audit_event_id"]


@pytest.mark.asyncio
async def test_create_refund_tier_boundary_l1(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={"work_order_id": wo_id, "amount": 1000, "refund_class": "labor", "reason": "x"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["tier"] == "L1"   # 邊界 1000 → L1


@pytest.mark.asyncio
async def test_create_refund_tier_l5(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={"work_order_id": wo_id, "amount": 150000, "refund_class": "material", "reason": "x"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["tier"] == "L5"   # > 100000 → L5


@pytest.mark.asyncio
async def test_create_refund_sod_violation_403(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers, initiator=_SAME_UID, approver=_SAME_UID),
        json={"work_order_id": wo_id, "amount": 8000, "refund_class": "product", "reason": "x"},
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "SOD_VIOLATION"


@pytest.mark.asyncio
async def test_create_refund_missing_refund_class_422(make_wo, client, admin_headers):
    wo_id = await make_wo()
    # body schema 缺 refund_class → Pydantic 422（VALIDATION_ERROR）
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={"work_order_id": wo_id, "amount": 8000, "reason": "x"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_refund_invalid_refund_class_422(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={"work_order_id": wo_id, "amount": 8000, "refund_class": "bogus", "reason": "x"},
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "REFUND_CLASS_INVALID"


@pytest.mark.asyncio
async def test_create_refund_non_positive_amount_422(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers),
        json={"work_order_id": wo_id, "amount": 0, "refund_class": "product", "reason": "x"},
    )
    # amount gt=0 由 Pydantic 攔 → 422
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_refund_roundtrip(make_wo, client, admin_headers):
    wo_id = await make_wo()
    create = await client.post(
        _path(),
        headers=_sod_headers(admin_headers, executor=_EXECUTOR_UID),
        json={"work_order_id": wo_id, "amount": 40000, "refund_class": "travel", "reason": "x"},
    )
    assert create.status_code == 200, create.text
    refund_id = create.json()["data"]["refund_id"]

    got = await client.get(f"{_path()}/{refund_id}", headers=admin_headers)
    assert got.status_code == 200, got.text
    data = got.json()["data"]
    assert data["tier"] == "L4"           # 30000 < 40000 <= 100000 → L4
    assert data["refund_class"] == "travel"
    assert data["executor_user_id"] == _EXECUTOR_UID
