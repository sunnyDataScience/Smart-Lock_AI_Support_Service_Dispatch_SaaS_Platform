"""CR-0030 派工模式切換測試。

- 純函式：via_for_mode 映射（platform_paid→platform）
- component：set/get dispatch_mode round-trip + 非法 422
- component：platform_paid 模式下 assign_order → work_orders.dispatched_via='platform'
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import dispatch_mode_service, work_order_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def test_via_for_mode_mapping():
    assert dispatch_mode_service.via_for_mode("manual") == "manual"
    assert dispatch_mode_service.via_for_mode("platform_paid") == "platform"
    assert dispatch_mode_service.via_for_mode("auto_match") == "auto_match"
    assert dispatch_mode_service.via_for_mode("bogus") == "manual"  # fallback


@pytest.mark.asyncio
async def test_set_get_dispatch_mode_roundtrip(client):
    assert await db_module._ensure_conn()
    try:
        await dispatch_mode_service.set_dispatch_mode(
            tenant_id=DEFAULT_TENANT_ID, mode="platform_paid")
        assert await dispatch_mode_service.get_dispatch_mode(DEFAULT_TENANT_ID) == "platform_paid"
        with pytest.raises(ApiError) as ei:
            await dispatch_mode_service.set_dispatch_mode(
                tenant_id=DEFAULT_TENANT_ID, mode="bogus")
        assert ei.value.status_code == 422
    finally:
        # 還原共享租戶設定，避免影響其他測試
        await dispatch_mode_service.set_dispatch_mode(
            tenant_id=DEFAULT_TENANT_ID, mode="manual")


async def _seed_wo_and_tech() -> tuple[str, str, list]:
    """seed dispatch-ready WO + active technician（同租戶）。回 (wo_id, tech_id, cleanup_ids)。"""
    uid = str(uuid.uuid4()); cid = str(uuid.uuid4()); pcid = str(uuid.uuid4())
    woid = str(uuid.uuid4()); tuid = str(uuid.uuid4()); tid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')",
        (uid, DEFAULT_TENANT_ID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)",
        (cid, uid, f"sess-{uid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status, brand, model, category) "
        "VALUES (%s::uuid, %s::uuid, 'confirmed', 'Yale', 'YDM-4109', '電池')", (pcid, cid))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_address, brand, model, problem_type) "
        "VALUES (%s::uuid, %s::uuid, 'created', '新北市板橋區文化路1號', 'Yale', 'YDM-4109', '電池故障')",
        (woid, pcid))
    # active technician（同租戶）
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'technician')",
        (tuid, DEFAULT_TENANT_ID))
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, email, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '測試師傅', '0911222333', %s, 'active')",
        (tid, DEFAULT_TENANT_ID, tuid, f"tech-{tuid[:8]}@example.com"))
    return woid, tid, [woid, pcid, cid, uid, tid, tuid]


async def _cleanup(ids: list) -> None:
    woid, pcid, cid, uid, tid, tuid = ids
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pcid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM technicians WHERE id = %s::uuid", (tid,))
    await db_module._conn.execute("DELETE FROM users WHERE id IN (%s::uuid, %s::uuid)", (uid, tuid))


@pytest.mark.asyncio
async def test_assign_under_platform_paid_marks_dispatched_via(client):
    assert await db_module._ensure_conn()
    woid, tid, ids = await _seed_wo_and_tech()
    try:
        await dispatch_mode_service.set_dispatch_mode(
            tenant_id=DEFAULT_TENANT_ID, mode="platform_paid")
        await work_order_service.assign_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=woid, technician_id=tid,
            reason_code="manual")
        cur = await db_module._conn.execute(
            "SELECT dispatched_via FROM work_orders WHERE id = %s::uuid", (woid,))
        assert (await cur.fetchone())[0] == "platform"
    finally:
        await dispatch_mode_service.set_dispatch_mode(
            tenant_id=DEFAULT_TENANT_ID, mode="manual")
        await _cleanup(ids)
