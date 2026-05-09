"""F-015 createWarrantyClaim integration tests（dual-trigger pattern）。

測試矩陣：
  1. Happy path with WO: customer + brand + model + claim_type → 201 + WC doc no
  2. Happy path without WO: customer 主動 LINE 申訴（無 WO）→ 201
  3. Idempotency: 同 (work_order_id, claim_type) 二次 → 200 + 同 id
  4. 不同 claim_type 同 WO → 兩筆獨立
  5. Customer not found → 404
  6. Tenant isolation: 跨 tenant customer → 404
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def insert_customer_and_wo(client):
    """建 customer + (optional) WO chain。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "wo": [], "pc": [], "conv": [], "user": [],
    }

    async def _factory(
        *, tenant_id: str = DEFAULT_TENANT_ID, with_wo: bool = True,
    ) -> dict:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, role) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user')",
            (user_id, tenant_id, f"U{user_id.replace('-', '')}"),
        )
        created["user"].append(user_id)

        wo_id = None
        if with_wo:
            conv_id = str(uuid.uuid4())
            pc_id = str(uuid.uuid4())
            wo_id = str(uuid.uuid4())
            await db_module._conn.execute(
                "INSERT INTO conversations (id, user_id, status, session_id) "
                "VALUES (%s::uuid, %s::uuid, 'active', %s)",
                (conv_id, user_id, f"warr-test-{conv_id[:8]}"),
            )
            created["conv"].append(conv_id)
            await db_module._conn.execute(
                "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
                "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDR-1', 'confirmed')",
                (pc_id, conv_id),
            )
            created["pc"].append(pc_id)
            await db_module._conn.execute(
                "INSERT INTO work_orders (id, problem_card_id, status, customer_address, priority) "
                "VALUES (%s::uuid, %s::uuid, 'completed', '台北市中正區test', 'normal')",
                (wo_id, pc_id),
            )
            created["wo"].append(wo_id)
        return {"user_id": user_id, "wo_id": wo_id}

    yield _factory

    await _ensure_conn()
    for u_id in created["user"]:
        await db_module._conn.execute(
            "DELETE FROM warranty_claims WHERE customer_id = %s::uuid",
            (u_id,),
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
async def test_create_happy_path_with_wo(
    client, admin_headers, insert_customer_and_wo,
):
    chain = await insert_customer_and_wo(with_wo=True)
    res = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "customer_id": chain["user_id"],
            "work_order_id": chain["wo_id"],
            "device_brand": "Yale",
            "device_model": "YDR-1",
            "claim_type": "defective",
            "requested_by_role": "customer_service",
            "dispute_reason": "鎖頭故障",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["customer_id"] == chain["user_id"]
    assert data["work_order_id"] == chain["wo_id"]


@pytest.mark.asyncio
async def test_create_happy_path_without_wo(
    client, admin_headers, insert_customer_and_wo,
):
    chain = await insert_customer_and_wo(with_wo=False)
    res = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "customer_id": chain["user_id"],
            "device_brand": "Samsung",
            "device_model": "SHP-1",
            "claim_type": "missing_parts",
            "requested_by_role": "customer_via_line",
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["work_order_id"] is None


@pytest.mark.asyncio
async def test_create_idempotent_same_claim_type(
    client, admin_headers, insert_customer_and_wo,
):
    chain = await insert_customer_and_wo(with_wo=True)
    headers = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
    body = {
        "customer_id": chain["user_id"],
        "work_order_id": chain["wo_id"],
        "device_brand": "X", "device_model": "Y",
        "claim_type": "malfunction",
        "requested_by_role": "customer_service",
    }
    res1 = await client.post("/api/v1/warranty-claims", headers=headers, json=body)
    assert res1.status_code == 201
    cid1 = res1.json()["data"]["id"]

    res2 = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == cid1


@pytest.mark.asyncio
async def test_create_diff_claim_type_creates_new(
    client, admin_headers, insert_customer_and_wo,
):
    chain = await insert_customer_and_wo(with_wo=True)
    base = {
        "customer_id": chain["user_id"],
        "work_order_id": chain["wo_id"],
        "device_brand": "X", "device_model": "Y",
        "requested_by_role": "customer_service",
    }
    res1 = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**base, "claim_type": "defective"},
    )
    res2 = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**base, "claim_type": "premature_failure"},
    )
    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["data"]["id"] != res2.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_customer_not_found(client, admin_headers):
    res = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "customer_id": str(uuid.uuid4()),
            "device_brand": "X", "device_model": "Y",
            "claim_type": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_cross_tenant_404(
    client, admin_headers, insert_customer_and_wo,
):
    other = "00000000-0000-0000-0000-000000000099"
    chain = await insert_customer_and_wo(with_wo=False, tenant_id=other)
    res = await client.post(
        "/api/v1/warranty-claims",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "customer_id": chain["user_id"],
            "device_brand": "X", "device_model": "Y",
            "claim_type": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404
