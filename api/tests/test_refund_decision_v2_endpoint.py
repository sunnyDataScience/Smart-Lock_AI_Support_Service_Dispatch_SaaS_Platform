"""Refund Decision v2 端點整合測試（CR-0003 P1-T4/Q4）。

測試矩陣：
  1. approve（requires_dual_sign=False）→ 200, status=approved
  2. reject（requires_dual_sign=False）→ 200, status=rejected
  3. Idempotency-Key replay → 200（冪等回放）
  4. cross-tenant → 403 CROSS_TENANT_WRITE
  5. 雙簽第一步 approve → 200, status=csm_approved
  6. 已完成狀態再 decide → 409 STATE_CONFLICT

路徑：POST /tenants/{tenantId}/refunds/{refundId}/decision
Service：refund_service.submit_decision（零業務邏輯重寫）

⚠ 本檔為 @pytest.mark.component，需 live DB（dev 環境 lock_AI_data）。
  若 DB 不可用，這些測試會在 fixture 階段 error/skip — 屬預期。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

# SoD 行為人 UUID（避免 InvalidTextRepresentation，對齊 test_refund_sod_endpoint）
_INITIATOR_UID = "a0000000-0000-4000-8000-000000000011"
_APPROVER_UID = "a0000000-0000-4000-8000-000000000012"

# 其他 tenant（cross-tenant guard 測試用）
_OTHER_TENANT_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"


@pytest_asyncio.fixture
async def insert_refund_for_decision(client, admin_headers):
    """工廠 fixture：在 live DB 建立 refund_request（含 work_order chain）。

    refund_service._TENANT_JOIN 透過 work_order → problem_card → conversation →
    user 的 4-JOIN 鏈做 tenant 隔離；fixture 必須建立完整 chain。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "refund": [],
        "wo": [],
        "pc": [],
        "conv": [],
    }

    async def _factory(*, amount: float = 1000.0, requires_dual_sign: bool = False) -> str:
        await _ensure_conn()
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        rid = str(uuid.uuid4())

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"dec-v2-{conv_id[:8]}"),
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
            "VALUES (%s::uuid, %s::uuid, 'completed', '台北市中正區test', 'normal')",
            (wo_id, pc_id),
        )
        created["wo"].append(wo_id)

        await db_module._conn.execute(
            "INSERT INTO refund_requests "
            "  (id, work_order_id, requested_by, amount, reason, status, requires_dual_sign) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', %s)",
            (rid, wo_id, ADMIN_USER_ID, amount, "test-dec-v2-fixture", requires_dual_sign),
        )
        created["refund"].append(rid)
        return rid

    yield _factory

    # cleanup（依 FK 反序）
    from core.db import _ensure_conn as _ec
    await _ec()
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


def _decision_path(tenant_id: str, refund_id: str) -> str:
    return f"/tenants/{tenant_id}/refunds/{refund_id}/decision"


def _headers_with_idem(base_headers: dict) -> dict:
    """複製 base headers 並帶入 fresh Idempotency-Key（POST 必填）。"""
    return {**base_headers, "Idempotency-Key": str(uuid.uuid4())}


# ---------------------------------------------------------------------------
# approve（單簽）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_approve_single_sign(
    client, admin_headers, insert_refund_for_decision
):
    """approve（requires_dual_sign=False）→ 200, status=approved。"""
    rid = await insert_refund_for_decision(amount=500.0, requires_dual_sign=False)
    res = await client.post(
        _decision_path(DEFAULT_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),
        json={"decision": "approve", "reason": "核准退款"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "approved"
    assert data["id"] == rid


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_reject(
    client, admin_headers, insert_refund_for_decision
):
    """reject → 200, status=rejected。"""
    rid = await insert_refund_for_decision(amount=800.0, requires_dual_sign=False)
    res = await client.post(
        _decision_path(DEFAULT_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),
        json={"decision": "reject", "reason": "不符資格"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# Idempotency-Key replay
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_idempotency_replay(
    client, admin_headers, insert_refund_for_decision
):
    """同一 Idempotency-Key 重複送 → 200 冪等回放，不重複改狀態。"""
    rid = await insert_refund_for_decision(amount=600.0, requires_dual_sign=False)
    idem_key = str(uuid.uuid4())
    headers = {**admin_headers, "Idempotency-Key": idem_key}
    body = {"decision": "approve", "reason": "replay test"}

    res1 = await client.post(_decision_path(DEFAULT_TENANT_ID, rid), headers=headers, json=body)
    assert res1.status_code == 200, res1.text

    # 相同 key + 相同 body → replay 回相同 200
    res2 = await client.post(_decision_path(DEFAULT_TENANT_ID, rid), headers=headers, json=body)
    assert res2.status_code == 200, res2.text
    assert res2.json()["data"]["status"] == "approved"


# ---------------------------------------------------------------------------
# cross-tenant guard → 403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_cross_tenant_403(
    client, admin_headers, insert_refund_for_decision
):
    """path tenantId 與 JWT claim 不同 → 403 CROSS_TENANT_WRITE。"""
    rid = await insert_refund_for_decision(amount=300.0, requires_dual_sign=False)
    res = await client.post(
        # 用其他 tenant ID 在 path 中
        _decision_path(_OTHER_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),
        json={"decision": "approve", "reason": "x"},
    )
    assert res.status_code == 403, res.text
    assert res.json()["error_code"] == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 雙簽：第一步 → csm_approved
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_dual_sign_first_step(
    client, admin_headers, insert_refund_for_decision
):
    """requires_dual_sign=True，第一簽 → 200, status=csm_approved。"""
    rid = await insert_refund_for_decision(amount=50000.0, requires_dual_sign=True)
    res = await client.post(
        _decision_path(DEFAULT_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),
        json={"decision": "approve", "reason": "first sign ok"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "csm_approved"


# ---------------------------------------------------------------------------
# 終態再 decide → 409 STATE_CONFLICT
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_decision_v2_state_conflict_409(
    client, admin_headers, insert_refund_for_decision
):
    """已 approved 再送 decision → 409 STATE_CONFLICT。"""
    rid = await insert_refund_for_decision(amount=200.0, requires_dual_sign=False)

    # 第一次 approve 成功
    res1 = await client.post(
        _decision_path(DEFAULT_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),
        json={"decision": "approve", "reason": "ok"},
    )
    assert res1.status_code == 200, res1.text

    # 再次送 → 409（idempotency 會先命中 — 用不同 key 繞過 replay 觸發 STATE_CONFLICT）
    res2 = await client.post(
        _decision_path(DEFAULT_TENANT_ID, rid),
        headers=_headers_with_idem(admin_headers),  # fresh key
        json={"decision": "approve", "reason": "again"},
    )
    assert res2.status_code == 409, res2.text
    assert res2.json()["error_code"] == "STATE_CONFLICT"
