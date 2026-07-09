"""CR-0053 到場事件修復測試（door-check 前置閘 + arrival KPI started_at）。

修：onsite_arrival 原誤呼 record_door_check（寫 'door_check'）→ submit_door_check_v2
查 event_type='arrival' 恆 409、started_at 不落。改 record_arrival 正確寫 'arrival' + started_at。
"""
from __future__ import annotations
import uuid
import pytest

from tests.conftest import seed_accepted_quote
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo_in_progress() -> tuple[str, str, str]:
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, '客', '0912000000', '台北市信義區1號', 'line_user')", (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDM', '維修', 'normal', 'confirmed')", (pid, cid))
    await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    await db_module._conn.execute(
        "UPDATE work_orders SET status='accepted' WHERE id=%s::uuid", (wo["id"],))
    return wo["id"], uid, pid


async def _cleanup(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_doorcheck_blocked_before_arrival_then_passes_after():
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo_in_progress()
    try:
        # 到場前：door-check 前置閘 409（gate 真的有作用）
        with pytest.raises(ApiError) as ei:
            await svc.submit_door_check_v2(tenant_id=TID, wo_id=wid, checklist={"x": 1})
        assert ei.value.status_code == 409

        # 到場：寫 arrival 事件 + 補 started_at（→ actual_arrival 出現在 dict）
        order = await svc.record_arrival(
            tenant_id=TID, wo_id=wid, arrived_at="2026-06-20T10:00:00Z",
            gps={"lat": 25.03, "lng": 121.56})
        assert order.get("actual_arrival") is not None  # CR-0053 bug2：started_at 已落

        # 到場後：door-check 通過（CR-0053 bug1：gate 不再恆 409）
        out = await svc.submit_door_check_v2(tenant_id=TID, wo_id=wid, checklist={"ok": True})
        assert out.get("id") == wid
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_reassign_writes_event_no_500():
    """CR-0053 同類修復：reassign 寫 event_type='reassign'，CHECK 補後不再 CheckViolation。"""
    assert await db_module._ensure_conn()
    # 取兩個 active 技師
    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE tenant_id=%s::uuid AND status='active' LIMIT 2", (TID,))
    techs = [str(r[0]) for r in await cur.fetchall()]
    if len(techs) < 2:
        pytest.skip("需要 2 個 active 技師")
    wid, uid, pid = await _seed_wo_in_progress()
    try:
        # 指派 tech0 + 設 assigned
        await db_module._conn.execute(
            "UPDATE work_orders SET status='assigned', technician_id=%s::uuid WHERE id=%s::uuid",
            (techs[0], wid))
        # 改派 tech1 → 應成功且寫 'reassign' event（修前會 CheckViolation 500）
        out = await svc.reassign_order(
            tenant_id=TID, wo_id=wid, new_technician_id=techs[1], reason="客戶要求換師傅")
        assert out.get("id") == wid
        ev = await db_module._conn.execute(
            "SELECT 1 FROM work_order_events WHERE work_order_id=%s::uuid AND event_type='reassign'", (wid,))
        assert await ev.fetchone() is not None  # event 真的寫進去了
    finally:
        await _cleanup(uid, pid)
