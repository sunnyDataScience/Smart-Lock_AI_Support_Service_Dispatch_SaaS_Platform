"""F-014 createRefundRequest integration tests（dual-trigger pattern）。

測試矩陣：
  1. Happy path: WO 存在 → 201 + new refund + RM-YYYYMMDD-NNNN doc number
  2. Idempotency: 同 (work_order_id, reason_code) 二次呼叫 → 200 + 同 refund id
  3. 不同 reason_code 同 WO → 兩筆獨立 refund
  4. Auto dual-sign: amount >= 100,000 → requires_dual_sign=True
  5. Auto dual-sign: amount < 100,000 → requires_dual_sign=False
  6. Caller override: requires_dual_sign=true → 強制雙簽 (即使金額未達)
  7. WO not found → 404
  8. Tenant isolation: 跨 tenant → 404
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def insert_wo_chain(client):
    """建 conversation→pc→wo chain，回 wo_id（refund 測試用）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"wo": [], "pc": [], "conv": [], "user": []}

    async def _factory(*, tenant_id: str = DEFAULT_TENANT_ID) -> str:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())

        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, role) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user')",
            (user_id, tenant_id, f"U{user_id.replace('-', '')}"),
        )
        created["user"].append(user_id)

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, user_id, f"refund-test-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)

        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid, %s::uuid, 'Test', 'TM', 'confirmed')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)

        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, priority) "
            "VALUES (%s::uuid, %s::uuid, 'completed', '台北市中正區test', 'normal')",
            (wo_id, pc_id),
        )
        created["wo"].append(wo_id)
        return wo_id

    yield _factory

    # cleanup（FK 反序）
    await _ensure_conn()
    for wo_id in created["wo"]:
        await db_module._conn.execute(
            "DELETE FROM refund_requests WHERE work_order_id = %s::uuid",
            (wo_id,),
        )
    for table, ids in [
        ("work_orders", created["wo"]),
        ("problem_cards", created["pc"]),
        ("conversations", created["conv"]),
        ("users", created["user"]),
    ]:
        if ids:
            await db_module._conn.execute(
                f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,)
            )


@pytest.mark.asyncio
async def test_create_happy_path(client, admin_headers, insert_wo_chain):
    wo_id = await insert_wo_chain()
    res = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id,
            "amount": "1500.00",
            "reason": "客戶反應商品瑕疵",
            "reason_code": "defective_product",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["work_order_id"] == wo_id
    assert data["status"] == "pending"
    # 金額 1500 < 100,000 → dual_sign auto False
    assert data["requires_dual_sign"] is False


@pytest.mark.asyncio
async def test_create_idempotent_same_reason(
    client, admin_headers, insert_wo_chain,
):
    wo_id = await insert_wo_chain()
    res1 = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id,
            "amount": "500",
            "reason": "first attempt",
            "reason_code": "service_quality",
            "requested_by_role": "customer_service",
        },
    )
    assert res1.status_code == 201
    rid1 = res1.json()["data"]["id"]

    res2 = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id,
            "amount": "999",
            "reason": "second attempt with diff amount",
            "reason_code": "service_quality",
            "requested_by_role": "customer_via_line",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == rid1  # 同 reason_code → 既存


@pytest.mark.asyncio
async def test_create_diff_reason_creates_new(
    client, admin_headers, insert_wo_chain,
):
    wo_id = await insert_wo_chain()
    res1 = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id, "amount": "100", "reason": "x",
            "reason_code": "billing_error",
            "requested_by_role": "customer_service",
        },
    )
    res2 = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id, "amount": "200", "reason": "y",
            "reason_code": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["data"]["id"] != res2.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_auto_dual_sign_high_amount(
    client, admin_headers, insert_wo_chain,
):
    wo_id = await insert_wo_chain()
    res = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id, "amount": "150000.00",
            "reason": "high value", "reason_code": "defective_product",
            "requested_by_role": "manager",
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["requires_dual_sign"] is True


@pytest.mark.asyncio
async def test_create_caller_override_dual_sign(
    client, admin_headers, insert_wo_chain,
):
    wo_id = await insert_wo_chain()
    res = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id, "amount": "50",
            "reason": "x", "reason_code": "other",
            "requested_by_role": "customer_service",
            "requires_dual_sign": True,
        },
    )
    assert res.status_code == 201
    # caller 強制雙簽，覆蓋 auto-determine
    assert res.json()["data"]["requires_dual_sign"] is True


@pytest.mark.asyncio
async def test_create_wo_not_found(client, admin_headers):
    res = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": str(uuid.uuid4()),
            "amount": "100", "reason": "x",
            "reason_code": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_cross_tenant_404(client, admin_headers, insert_wo_chain):
    other_tenant = "00000000-0000-0000-0000-000000000099"
    wo_id = await insert_wo_chain(tenant_id=other_tenant)
    res = await client.post(
        "/api/v1/refunds",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "work_order_id": wo_id, "amount": "100",
            "reason": "x", "reason_code": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404
