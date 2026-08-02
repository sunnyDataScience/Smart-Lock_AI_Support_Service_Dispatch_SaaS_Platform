"""CR-0164 D：GDPR forget 三缺口修復（component，live DB）。

- legal-hold 前置擋（名下 legal_hold media → 423 LEGAL_HOLD_ACTIVE + audit blocked）。
- 全流程 append-only audit（create/soft/hard 皆寫 audit_events）。
- 匿名化即終態（方案 A）：hard_delete 遇 FK 阻擋不假性成功，physical_deleted=false。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import gdpr_forget_service as svc
from tests.conftest import DEFAULT_TENANT_ID, audit_privileged_exec

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


async def _mk_subject() -> str:
    assert await db_module._ensure_conn()
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, email, phone, role) "
        "VALUES (%s::uuid, %s::uuid, %s, '被遺忘客', %s, '0912345678', 'customer')",
        (uid, TID, f"Ucr0164g{uuid.uuid4().hex[:14]}", f"forget-{uid[:8]}@ex.com"))
    return uid


async def _cleanup(uid: str) -> None:
    await audit_privileged_exec("DELETE FROM audit_events WHERE target_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM saas.forget_request WHERE subject_user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM media_files WHERE uploader_user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM complaints WHERE customer_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_legal_hold_blocks_soft_delete_with_423_and_audit():
    """名下有 legal_hold media → soft_delete 423 + audit gdpr_forget_blocked。"""
    uid = await _mk_subject()
    try:
        await db_module._conn.execute(
            "INSERT INTO media_files (tenant_id, uploader_user_id, purpose, filename, "
            " content_type, size_bytes, storage_path, legal_hold) "
            "VALUES (%s::uuid, %s::uuid, 'dispute_evidence_customer', 'e.jpg', 'image/jpeg', 1000, '/x/e.jpg', TRUE)", (TID, uid))
        req = await svc.create_forget_request(
            tenant_id=TID, subject_user_id=uid, requested_by="customer_self", actor_user_id=None)
        with pytest.raises(ApiError) as exc:
            await svc.soft_delete(request_id=req["id"], tenant_id=TID, actor_user_id=None)
        assert exc.value.status_code == 423
        assert exc.value.error_code == "LEGAL_HOLD_ACTIVE"
        blk = await (await db_module._conn.execute(
            "SELECT count(*) FROM audit_events WHERE target_id=%s::uuid "
            "AND action='gdpr_forget_blocked'", (uid,))).fetchone()
        assert blk[0] >= 1, "legal-hold 擋下應寫 gdpr_forget_blocked audit"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_forget_flow_writes_audit():
    """create + soft_delete 皆寫 append-only audit（原全程零稽核）。"""
    uid = await _mk_subject()
    try:
        req = await svc.create_forget_request(
            tenant_id=TID, subject_user_id=uid, requested_by="dpo", actor_user_id=None)
        await svc.soft_delete(request_id=req["id"], tenant_id=TID, actor_user_id=None)
        rows = await (await db_module._conn.execute(
            "SELECT action FROM audit_events WHERE target_id=%s::uuid ORDER BY created_at", (uid,))).fetchall()
        actions = {r[0] for r in rows}
        assert "gdpr_forget_received" in actions
        assert "gdpr_forget_soft_deleted" in actions
        # PII 已匿名化
        u = await (await db_module._conn.execute(
            "SELECT display_name, phone FROM users WHERE id=%s::uuid", (uid,))).fetchone()
        assert u[0] == "[REDACTED]" and u[1] is None
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_hard_delete_fk_blocked_anonymized_retained():
    """FK 阻擋（complaints 引用）→ 不假性成功：status=hard_deleted 但 physical_deleted=false、user 列仍在（已匿名）。"""
    uid = await _mk_subject()
    try:
        # 建 complaint 引用 subject（NO ACTION FK → 阻擋實體刪除）
        await db_module._conn.execute(
            "INSERT INTO complaints (customer_id, category, description) "
            "VALUES (%s::uuid, 'service', '測試客訴')", (uid,))
        req = await svc.create_forget_request(
            tenant_id=TID, subject_user_id=uid, requested_by="admin", actor_user_id=None)
        await svc.soft_delete(request_id=req["id"], tenant_id=TID, actor_user_id=None)
        # 讓 cooldown 立即過
        await db_module._conn.execute(
            "UPDATE saas.forget_request SET hard_delete_eligible_at=NOW()-INTERVAL '1 day' "
            "WHERE id=%s::uuid", (req["id"],))
        out = await svc.hard_delete(request_id=req["id"], tenant_id=TID, actor_user_id=None)
        assert out["status"] == "hard_deleted"
        # user 列仍在（FK 擋、匿名化終態），非假性刪除
        still = await (await db_module._conn.execute(
            "SELECT display_name FROM users WHERE id=%s::uuid", (uid,))).fetchone()
        assert still is not None and still[0] == "[REDACTED]"
        # audit 記實際 disposition
        aud = await (await db_module._conn.execute(
            "SELECT payload->>'disposition' FROM audit_events WHERE target_id=%s::uuid "
            "AND action='gdpr_forget_hard_deleted'", (uid,))).fetchone()
        assert aud[0] == "anonymized_retained_fk"
    finally:
        await _cleanup(uid)
