"""到場即開工（accepted → in_progress）— CR-0205 D1(a)。

WHY：`in_progress` 在此之前是**死值**。正常工單走 assigned → accepted → completed，
`_WO_TRANSITIONS` 裡 accepted→in_progress 那條邊沒有任何人走。連帶三個後果：
  ① 統計桶（work_order_service.py:590-604）的「施工中」恆為 0
  ② technician_service.py:512-518 的可派技師數以
     `NOT EXISTS (... wo.status = 'in_progress')` 排除在場師傅 —— 該排除從未觸發，
     **營運看到的可派人力一直是高估的**
  ③ requote_service._ALLOWED_WO_STATUS = {"in_progress"}（:23）
     → **現場加價整條路徑不可達**

業主已於 `15_SDS.md:221` 裁決 `on_site ≡ in_progress`，本修正是該裁決的落地。

seed 方式沿用 `test_cr_0053_arrival_doorcheck.py` 的既有做法（含 CR-0128
報價先行 gate 的前置 `seed_accepted_quote`），避免另造一套。
"""
from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import work_order_service as svc
from tests.conftest import seed_accepted_quote

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo(status: str) -> tuple[str, str, str]:
    """建一張指定狀態的工單，回 (wo_id, user_id, pc_id)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, '客', '0912000000', '台北市信義區1號', 'line_user')",
        (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDM', '維修', 'normal', 'confirmed')", (pid, cid))
    await seed_accepted_quote(pid, TID)
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    await db_module._conn.execute(
        "UPDATE work_orders SET status=%s WHERE id=%s::uuid", (status, wo["id"]))
    return wo["id"], uid, pid


async def _cleanup(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(
        f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(
        f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


async def _status_of(wo_id: str) -> str:
    cur = await db_module._conn.execute(
        "SELECT status FROM work_orders WHERE id = %s::uuid", (wo_id,))
    row = await cur.fetchone()
    return row[0]


@pytest.mark.asyncio
async def test_arrival_transitions_accepted_to_in_progress():
    """accepted 狀態到場 → status 轉 in_progress，且 started_at 落點。"""
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo("accepted")
    try:
        await svc.record_arrival(tenant_id=TID, wo_id=wid)
        assert await _status_of(wid) == "in_progress", (
            "到場未轉施工中 —— in_progress 會退回死值，統計桶恆 0、"
            "可派技師數高估、現場加價不可達"
        )
        cur = await db_module._conn.execute(
            "SELECT started_at FROM work_orders WHERE id = %s::uuid", (wid,))
        assert (await cur.fetchone())[0] is not None
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_arrival_from_assigned_keeps_status():
    """assigned 到場**刻意不轉**（技師未接單就到場屬異常流程，CR-0205 D1 標另議）。"""
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo("assigned")
    try:
        await svc.record_arrival(tenant_id=TID, wo_id=wid)
        assert await _status_of(wid) == "assigned"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_arrival_is_idempotent_on_in_progress():
    """已在 in_progress 重複到場 → CASE 落 ELSE，維持原狀且不報錯。"""
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo("accepted")
    try:
        await svc.record_arrival(tenant_id=TID, wo_id=wid)
        await svc.record_arrival(tenant_id=TID, wo_id=wid)
        assert await _status_of(wid) == "in_progress"
    finally:
        await _cleanup(uid, pid)
