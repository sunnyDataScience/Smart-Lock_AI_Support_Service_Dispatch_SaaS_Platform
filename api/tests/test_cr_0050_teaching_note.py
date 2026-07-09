"""CR-0050 完工套件教學紀錄測試（BR-M08-03）。"""
from __future__ import annotations
import uuid
import pytest

from tests.conftest import seed_accepted_quote
import core.db as db_module
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _seed_confirmed_pc() -> tuple[str, str]:
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
    return pid, uid


async def _cleanup(uid: str, pid: str) -> None:
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_complete_stores_teaching_note():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        await db_module._conn.execute(
            "UPDATE work_orders SET status='in_progress' WHERE id=%s::uuid", (wo["id"],))
        out = await svc.complete_order(
            tenant_id=TID, wo_id=wo["id"], summary="完工",
            is_override=True, actor_role="admin", override_reason="測試",
            teaching_note="已教客戶換電池與重設密碼")
        assert out["teaching_note"] == "已教客戶換電池與重設密碼"
    finally:
        await _cleanup(uid, pid)
