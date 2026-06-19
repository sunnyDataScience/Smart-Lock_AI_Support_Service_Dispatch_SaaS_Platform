"""CR-0055 Evidence package 聚合測試。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services import evidence_package_service as eps

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
_SEED_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _seed_wo() -> tuple[str, str, str]:
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
    from services import work_order_service as svc
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    return wo["id"], uid, pid


async def _cleanup(uid, pid, wid):
    await db_module._conn.execute("DELETE FROM digital_signatures WHERE document_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM media_files WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_order_events WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_evidence_package_aggregates():
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo()
    try:
        # 客戶簽名 + 一張完工照
        await db_module._conn.execute(
            "INSERT INTO digital_signatures (signer_id, signer_role, document_type, document_id, "
            "  signature_method, signature_data, integrity_hash) "
            "VALUES (%s, 'customer', 'work_order', %s::uuid, 'canvas', '{}'::jsonb, %s)",
            (_SEED_USER_ID, wid, f"h-{wid[:8]}"))
        await db_module._conn.execute(
            "INSERT INTO media_files (id, tenant_id, work_order_id, purpose, filename, content_type, size_bytes, storage_path, sha256) "
            "VALUES (gen_random_uuid(), %s::uuid, %s::uuid, 'completion_after', 'a.jpg', 'image/jpeg', 100, 's/a.jpg', 'x')",
            (TID, wid))
        pkg = await eps.get_evidence_package(tenant_id=TID, wo_id=wid, role="admin")
        assert pkg["work_order_id"] == wid
        assert pkg["summary"]["signature_count"] == 1
        assert pkg["summary"]["has_customer_signature"] is True
        assert pkg["summary"]["photo_count"] >= 1
    finally:
        await _cleanup(uid, pid, wid)
