"""CR-0062 事件驅動自動通知測試（完工→通知開單者）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
ADMIN = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _seed():
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'客','0912000000','台北市信義區1號','line_user')", (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-"+pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed')", (pid, cid))
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid, created_by=ADMIN)
    await db_module._conn.execute("UPDATE work_orders SET status='in_progress' WHERE id=%s::uuid", (wo["id"],))
    return wo["id"], uid, pid


@pytest.mark.asyncio
async def test_completion_auto_notifies_creator():
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed()
    try:
        await svc.complete_order(tenant_id=TID, wo_id=wid, summary="完工",
            is_override=True, actor_role="admin", override_reason="t")
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM notifications WHERE user_id=%s::uuid AND type='work_order_completed' "
            "AND created_at > now() - interval '1 minute'", (ADMIN,))
        assert (await cur.fetchone())[0] >= 1     # 開單者收到完工通知
    finally:
        await db_module._conn.execute("DELETE FROM notifications WHERE user_id=%s::uuid AND type='work_order_completed'", (ADMIN,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))
