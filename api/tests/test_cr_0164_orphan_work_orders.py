"""CR-0164 E：停權/終止技師的孤兒工單偵測+阻擋（component，live DB）。

原 suspend/terminate 只改 status 不查名下進行中工單 → 孤兒工單（客戶在途服務無人接手）。
修：偵測+阻擋——suspend 軟阻擋（force 可越過）、terminate 硬阻擋，須先改派。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import technician_lifecycle_service as svc

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


async def _mk_active_tech() -> tuple[str, str]:
    """建 active 技師（users+technicians），回 (tech_id, user_id)。"""
    assert await db_module._ensure_conn()
    uid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'E孤兒測試師傅', 'technician', TRUE)",
        (uid, TID, f"Ucr0164e{uuid.uuid4().hex[:14]}"))
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '孤兒測試師傅', '0912345678', 'active')",
        (tid, TID, uid))
    return tid, uid


async def _mk_wo(tech_id: str, status: str = "in_progress") -> tuple[str, str]:
    pid, wid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, "
        " customer_address, brand, model, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, '台北市孤兒路1號', 'Chatlock', 'A90', %s::uuid)",
        (wid, pid, status, tech_id, TID))
    return wid, pid


async def _cleanup(tid: str, uid: str, wids: list[tuple[str, str]]) -> None:
    for wid, pid in wids:
        await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid", (tid,))
    await db_module._conn.execute("DELETE FROM technicians WHERE id=%s::uuid", (tid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_suspend_blocked_by_orphan_work_order():
    """名下有 in_progress 工單 → suspend 409 TECHNICIAN_HAS_ACTIVE_WORK_ORDERS。"""
    tid, uid = await _mk_active_tech()
    wo = await _mk_wo(tid, "in_progress")
    try:
        with pytest.raises(ApiError) as exc:
            await svc.suspend(tenant_id=TID, tech_id=tid, actor_user_id=None, reason="測試停權")
        assert exc.value.status_code == 409
        assert exc.value.error_code == "TECHNICIAN_HAS_ACTIVE_WORK_ORDERS"
        # 未真的停權
        st = await (await db_module._conn.execute(
            "SELECT status FROM technicians WHERE id=%s::uuid", (tid,))).fetchone()
        assert st[0] == "active"
    finally:
        await _cleanup(tid, uid, [wo])


@pytest.mark.asyncio
async def test_suspend_force_overrides_orphan():
    """主管帶 force → 越過孤兒阻擋、成功停權（緊急安全閥）。"""
    tid, uid = await _mk_active_tech()
    wo = await _mk_wo(tid, "assigned")
    try:
        out = await svc.suspend(
            tenant_id=TID, tech_id=tid, actor_user_id=None, reason="緊急停權", force=True)
        assert out["new_status"] == "suspended"
    finally:
        await _cleanup(tid, uid, [wo])


@pytest.mark.asyncio
async def test_suspend_ok_without_orphan():
    """無進行中工單 → suspend 正常。"""
    tid, uid = await _mk_active_tech()
    try:
        out = await svc.suspend(tenant_id=TID, tech_id=tid, actor_user_id=None, reason="正常停權")
        assert out["new_status"] == "suspended"
    finally:
        await _cleanup(tid, uid, [])


@pytest.mark.asyncio
async def test_terminate_hard_blocked_by_orphan():
    """終止為終態、硬阻擋（無 force）：名下 accepted 工單 → 409。"""
    tid, uid = await _mk_active_tech()
    wo = await _mk_wo(tid, "accepted")
    try:
        with pytest.raises(ApiError) as exc:
            await svc.terminate(tenant_id=TID, tech_id=tid, actor_user_id=None, reason="測試終止")
        assert exc.value.status_code == 409
        assert exc.value.error_code == "TECHNICIAN_HAS_ACTIVE_WORK_ORDERS"
    finally:
        await _cleanup(tid, uid, [wo])
