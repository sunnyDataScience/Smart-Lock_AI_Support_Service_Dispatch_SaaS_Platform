"""CR-0049 pending scope change 阻擋完工測試（BR-M08-02 安全閘）。

報價/加價變更未經客戶確認（scope_changes.status='pending'）→ 技師不可完工（409）；
客戶確認/主管覆寫後放行。admin override 路徑可繞（不在本測試）。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

pytestmark = pytest.mark.component
_SEED_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _insert_wo(wo_id: str) -> None:
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, service_category) "
        "VALUES (%s::uuid, 'in_progress', '測試地址 1 號', 'repair')", (wo_id,))


async def _insert_customer_signature(wo_id: str) -> None:
    await db_module._conn.execute(
        "INSERT INTO digital_signatures (signer_id, signer_role, document_type, document_id, "
        "  signature_method, signature_data, integrity_hash) "
        "VALUES (%s, 'customer', 'work_order', %s::uuid, 'canvas', '{}'::jsonb, %s)",
        (_SEED_USER_ID, wo_id, f"hash-{wo_id[:8]}"))


async def _insert_pending_scope(wo_id: str, tech_id: str) -> None:
    await db_module._conn.execute(
        "INSERT INTO scope_changes (work_order_id, technician_id, reason, original_scope, "
        "  new_scope, original_price, status) "
        "VALUES (%s::uuid, %s::uuid, '現場發現額外工項', '{}'::jsonb, '{}'::jsonb, 1000, 'pending')",
        (wo_id, tech_id))


async def _a_technician_id() -> str:
    cur = await db_module._conn.execute("SELECT id FROM technicians LIMIT 1")
    row = await cur.fetchone()
    return str(row[0])


async def _cleanup(wo_id: str) -> None:
    await db_module._conn.execute("DELETE FROM scope_changes WHERE work_order_id = %s::uuid", (wo_id,))
    await db_module._conn.execute("DELETE FROM digital_signatures WHERE document_id = %s::uuid", (wo_id,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,))


async def _gate(wo_id: str):
    return await svc._enforce_completion_gate(
        wo_id=wo_id, summary="完工", photo_evidence_ids=["p1", "p2", "p3"],
        signature_evidence_id="sig", is_override=False, override_reason=None, actor_role=None)


@pytest.mark.asyncio
async def test_pending_scope_blocks_completion():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id)
    await _insert_customer_signature(wo_id)
    await _insert_pending_scope(wo_id, await _a_technician_id())
    try:
        with pytest.raises(ApiError) as ei:
            await _gate(wo_id)
        assert ei.value.status_code == 409
        assert ei.value.error_code == "PENDING_SCOPE_CHANGE"
        # 客戶確認後 → 放行
        await db_module._conn.execute(
            "UPDATE scope_changes SET status='customer_approved' WHERE work_order_id=%s::uuid", (wo_id,))
        assert await _gate(wo_id) == "完工"
    finally:
        await _cleanup(wo_id)


@pytest.mark.asyncio
async def test_no_scope_change_passes():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id)
    await _insert_customer_signature(wo_id)
    try:
        assert await _gate(wo_id) == "完工"
    finally:
        await _cleanup(wo_id)
