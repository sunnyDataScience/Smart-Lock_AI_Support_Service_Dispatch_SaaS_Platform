"""CR-0056 完工結案 Email 通道測試（best-effort，monkeypatch send_email）。"""
from __future__ import annotations
import uuid
import pytest

from tests.conftest import seed_accepted_quote
import core.db as db_module
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo_with_email(email: str) -> tuple[str, str, str]:
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, email, role) "
        "VALUES (%s::uuid, %s::uuid, '客', '0912000000', '台北市信義區1號', %s, 'line_user')",
        (uid, TID, email))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDM', '維修', 'normal', 'confirmed')", (pid, cid))
    await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    await db_module._conn.execute("UPDATE work_orders SET status='in_progress' WHERE id=%s::uuid", (wo["id"],))
    return wo["id"], uid, pid


async def _cleanup(uid, pid):
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_completion_sends_email_to_customer(monkeypatch):
    assert await db_module._ensure_conn()
    sent = {}
    def _fake_send(*, to, subject, body_text):
        sent["to"] = to; sent["subject"] = subject; return True
    from services import email_provider
    monkeypatch.setattr(email_provider, "send_email", _fake_send)

    email = f"cust-{uuid.uuid4().hex[:8]}@example.com"
    wid, uid, pid = await _seed_wo_with_email(email)
    try:
        await svc.complete_order(tenant_id=TID, wo_id=wid, summary="完工",
                                 is_override=True, actor_role="admin", override_reason="測試")
        assert sent.get("to") == email          # 結案 email 寄給客戶
        assert "完工" in sent.get("subject", "")
    finally:
        await _cleanup(uid, pid)
