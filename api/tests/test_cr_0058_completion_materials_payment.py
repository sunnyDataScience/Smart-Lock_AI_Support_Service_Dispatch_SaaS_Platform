"""CR-0058 完工套件 ④⑤ materials_used + payment_proof（欄位 + config 選用閘）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
_SEED_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _seed(in_progress=True):
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
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    await db_module._conn.execute("UPDATE work_orders SET status='in_progress' WHERE id=%s::uuid", (wo["id"],))
    return wo["id"], uid, pid


async def _sig(wid):
    await db_module._conn.execute(
        "INSERT INTO digital_signatures (signer_id, signer_role, document_type, document_id, "
        "  signature_method, signature_data, integrity_hash) "
        "VALUES (%s, 'customer', 'work_order', %s::uuid, 'canvas', '{}'::jsonb, %s)",
        (_SEED_USER_ID, wid, f"h-{wid[:8]}"))


async def _cleanup(uid, pid):
    await db_module._conn.execute("DELETE FROM digital_signatures WHERE document_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_override_stores_materials_payment():
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed()
    try:
        out = await svc.complete_order(tenant_id=TID, wo_id=wid, summary="完工",
            is_override=True, actor_role="admin", override_reason="t",
            materials_used="鎖芯 x1", payment_proof="現金末五碼 12345")
        cur = await db_module._conn.execute(
            "SELECT materials_used, payment_proof FROM work_orders WHERE id=%s::uuid", (wid,))
        r = await cur.fetchone()
        assert r[0] == "鎖芯 x1" and r[1] == "現金末五碼 12345"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_require_materials_gate(monkeypatch):
    assert await db_module._ensure_conn()
    from services import config_m18_service
    async def _cfg(*, namespace, key="default"):
        if namespace == "completion_policy":
            return {"require_materials": True, "min_photos": 0, "require_signature": True}
        return None
    monkeypatch.setattr(config_m18_service, "read_global_value", _cfg)
    wid, uid, pid = await _seed()
    try:
        await _sig(wid)
        # 技師正規完工但無用料 → 422（config require_materials on）
        with pytest.raises(ApiError) as ei:
            await svc.complete_order(tenant_id=TID, wo_id=wid, summary="完工",
                photo_evidence_ids=[], signature_evidence_id="s", is_override=False)
        assert ei.value.error_code == "MATERIALS_REQUIRED"
    finally:
        await _cleanup(uid, pid)
