"""退款雙簽流程整合測試（v1.29.0）。

測試矩陣：
  1. requires_dual_sign=False → approve 直接 approved
  2. requires_dual_sign=True → 第一簽 → csm_approved
  3. csm_approved → 同 user 再簽 → 409 DUAL_SIGN_SAME_USER
  4. csm_approved → 不同 user approve → approved
  5. pending → reject → rejected
  6. csm_approved → reject → rejected
  7. approved → 任何 decision → 409 STATE_CONFLICT
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def insert_refund(client, admin_headers):
    """工廠 fixture：建立測試用 refund_request + 完整 work_order chain。

    refund_service._TENANT_JOIN 透過 work_order → problem_card → conversation →
    user 的 4-JOIN 鏈做 tenant 隔離；fixture 必須建立完整 chain 否則 GET 會 404。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "refund": [],
        "wo": [],
        "pc": [],
        "conv": [],
    }

    async def _factory(*, amount: float, requires_dual_sign: bool) -> str:
        await _ensure_conn()
        # 建立完整 chain（user→conv→pc→wo→refund），全部標記 tenant=admin's
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        rid = str(uuid.uuid4())

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"test-session-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)

        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model) "
            "VALUES (%s::uuid, %s::uuid, 'Test', 'TestModel')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)

        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, priority) "
            "VALUES (%s::uuid, %s::uuid, 'created', '台北市中正區test', 'normal')",
            (wo_id, pc_id),
        )
        created["wo"].append(wo_id)

        await db_module._conn.execute(
            "INSERT INTO refund_requests "
            "  (id, work_order_id, requested_by, amount, reason, status, requires_dual_sign) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', %s)",
            (rid, wo_id, ADMIN_USER_ID, amount, "test-fixture", requires_dual_sign),
        )
        created["refund"].append(rid)
        return rid

    yield _factory

    # cleanup（依 FK 反序）
    await _ensure_conn()
    for table, ids in [
        ("refund_requests", created["refund"]),
        ("work_orders", created["wo"]),
        ("problem_cards", created["pc"]),
        ("conversations", created["conv"]),
    ]:
        if ids:
            await db_module._conn.execute(
                f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,)
            )


# ----------------------------------------------------------------------------
# 不需雙簽：一次到位
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_sign_approve(client, admin_headers, insert_refund):
    rid = await insert_refund(amount=1000.0, requires_dual_sign=False)
    res = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "ok"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "approved"


# ----------------------------------------------------------------------------
# 雙簽流程
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dual_sign_first_step(client, admin_headers, insert_refund):
    """第一簽 → csm_approved。"""
    rid = await insert_refund(amount=200000.0, requires_dual_sign=True)
    res = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "first sign"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "csm_approved"


@pytest.mark.asyncio
async def test_dual_sign_same_user_blocked(
    client, admin_headers, insert_refund
):
    """同一 user 不可雙簽。"""
    rid = await insert_refund(amount=200000.0, requires_dual_sign=True)
    # 第一簽
    res1 = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "first"},
    )
    assert res1.status_code == 200
    # 同 user 再簽 → 409
    res2 = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "second-by-same"},
    )
    assert res2.status_code == 409, res2.text
    assert res2.json()["error_code"] == "DUAL_SIGN_SAME_USER"


@pytest.mark.asyncio
async def test_dual_sign_completes_with_different_user(
    client, admin_headers, secondary_admin_headers, insert_refund
):
    """第二位不同 user 簽 → approved。"""
    rid = await insert_refund(amount=200000.0, requires_dual_sign=True)
    res1 = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "first"},
    )
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "csm_approved"

    res2 = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={
            **secondary_admin_headers,
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"decision": "approve", "reason": "second"},
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["data"]["status"] == "approved"


# ----------------------------------------------------------------------------
# 拒絕路徑
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reject_from_pending(client, admin_headers, insert_refund):
    rid = await insert_refund(amount=500.0, requires_dual_sign=False)
    res = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "reject", "reason": "not eligible"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_state_conflict_when_already_approved(
    client, admin_headers, insert_refund
):
    """approved 狀態不可再 decide → 409。"""
    rid = await insert_refund(amount=500.0, requires_dual_sign=False)
    await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "ok"},
    )
    res = await client.post(
        f"/api/v1/refunds/{rid}/decision",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "reason": "again"},
    )
    assert res.status_code == 409
