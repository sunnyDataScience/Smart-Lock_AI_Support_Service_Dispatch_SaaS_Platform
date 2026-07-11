"""CR-0166 R1：技師拒單端點（assigned → created 回派工池，UF-04/TC-DISPATCH-02）。"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import work_order_service as wo_svc
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"       # technicians.id
SEED_TECH_USER = "66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01"  # 對應 users.id
OTHER_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02"


async def _mk_assigned_wo(technician_id: str = SEED_TECH) -> tuple[str, str, str]:
    """建 user→conversation→pc→wo（status=assigned, technician_id=指定）。回 (wid,pid,uid)。"""
    assert await db_module._ensure_conn()
    wid, pid, uid, cid = (str(uuid.uuid4()) for _ in range(4))
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, role) "
        "VALUES (%s::uuid, %s::uuid, %s, '拒單測試客', 'customer')",
        (uid, TID, f"Ureject{uuid.uuid4().hex[:18]}"))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, f"sess-{cid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
        "VALUES (%s::uuid, %s, %s::uuid, 'Yale', 'A90', 'confirmed')", (pid, TID, cid))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, brand, model, "
        "customer_address, customer_name, problem_type, created_by, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'assigned', %s::uuid, 'Yale', 'A90', '台北市測試路1號', "
        "'測試客', '維修', %s::uuid, %s::uuid)",
        (wid, pid, technician_id, "c782bcfe-89bb-40b3-94b3-8c73d7bd0961", TID))
    return wid, pid, uid


async def _cleanup(wid: str, pid: str, uid: str) -> None:
    for sql in (
        "DELETE FROM dispatch_logs WHERE work_order_id=%s::uuid",
        "DELETE FROM work_order_events WHERE work_order_id=%s::uuid",
        "DELETE FROM work_orders WHERE id=%s::uuid",
    ):
        await db_module._conn.execute(sql, (wid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    cur = await db_module._conn.execute(
        "SELECT id FROM conversations WHERE user_id=%s::uuid", (uid,))
    for (cid,) in await cur.fetchall():
        await db_module._conn.execute("DELETE FROM conversations WHERE id=%s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_reject_returns_to_pool():
    """技師拒本人單 → 回 created、清 technician_id、寫 dispatch_logs+events。"""
    wid, pid, uid = await _mk_assigned_wo()
    try:
        out = await wo_svc.reject_order(
            tenant_id=TID, wo_id=wid, reason="今日已滿檔無法接",
            actor_user_id=SEED_TECH_USER, actor_role="technician")
        assert out["status"] in ("created", "inquiring")  # API 映射

        row = await (await db_module._conn.execute(
            "SELECT status, technician_id FROM work_orders WHERE id=%s::uuid", (wid,))).fetchone()
        assert row[0] == "created"
        assert row[1] is None  # 清空 technician_id

        dl = await (await db_module._conn.execute(
            "SELECT action, rejection_reason FROM dispatch_logs WHERE work_order_id=%s::uuid", (wid,))).fetchone()
        assert dl[0] == "reject"
        assert dl[1] == "今日已滿檔無法接"

        ev = await (await db_module._conn.execute(
            "SELECT event_type FROM work_order_events WHERE work_order_id=%s::uuid AND event_type='reject'", (wid,))).fetchone()
        assert ev is not None
    finally:
        await _cleanup(wid, pid, uid)


@pytest.mark.asyncio
async def test_reject_others_wo_409():
    """技師不能拒別人被派的單 → 409。"""
    wid, pid, uid = await _mk_assigned_wo(technician_id=OTHER_TECH)
    try:
        with pytest.raises(ApiError) as e:
            await wo_svc.reject_order(
                tenant_id=TID, wo_id=wid, reason="想搶這單",
                actor_user_id=SEED_TECH_USER, actor_role="technician")
        assert e.value.status_code == 409
    finally:
        await _cleanup(wid, pid, uid)


@pytest.mark.asyncio
async def test_reject_short_reason_422():
    wid, pid, uid = await _mk_assigned_wo()
    try:
        with pytest.raises(ApiError) as e:
            await wo_svc.reject_order(
                tenant_id=TID, wo_id=wid, reason="x",
                actor_user_id=SEED_TECH_USER, actor_role="technician")
        assert e.value.error_code == "VALIDATION_ERROR"
    finally:
        await _cleanup(wid, pid, uid)
