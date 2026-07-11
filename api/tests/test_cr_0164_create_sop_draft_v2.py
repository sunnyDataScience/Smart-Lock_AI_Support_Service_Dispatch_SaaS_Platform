"""CR-0164 F#5：createSopDraftV2 (POST /tenants/{tid}/sops/drafts) 500 修復。

Root cause：router 傳 title/steps/source_problem_card_id，但 sop_draft_service.create_draft
簽章為 source_case_id/source_type/draft_content/model_version → TypeError 500（端點 100% 壞），
且 create_draft 回 tuple 卻被當 dict 用。修為對齊 v1 sop_drafts.createSopDraft 契約。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


async def _mk_pc() -> tuple[str, str, str]:
    """建 user→conversation→resolved PC，回 (uid, cid, pid)。"""
    assert await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, role) "
        "VALUES (%s::uuid, %s::uuid, %s, 'line_user')", (uid, TID, f"Ucr0164{uuid.uuid4().hex[:16]}"))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, f"sop-{cid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDR-1', 'resolved')", (pid, cid))
    return uid, cid, pid


async def _cleanup(uid: str, cid: str, pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM sop_drafts WHERE source_problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id=%s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.asyncio
async def test_create_sop_draft_v2_no_longer_500(client, admin_headers):
    """對齊契約後回 201（原：任何呼叫 TypeError 500）。"""
    uid, cid, pid = await _mk_pc()
    try:
        body = {
            "source_case_id": pid,
            "source_type": "problem_card",
            "draft_content": "步驟一：斷電。步驟二：更換離合器模組。",
            "model_version": "gemini-2.5-flash@cr0164-test",
            "confidence_score": 0.9,
        }
        r = await client.post(
            f"/tenants/{TID}/sops/drafts", json=body,
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())})
        assert r.status_code == 201, r.text
        assert r.json()["id"]
    finally:
        await _cleanup(uid, cid, pid)


@pytest.mark.asyncio
async def test_create_sop_draft_v2_missing_content_422(client, admin_headers):
    """缺 draft_content → 422（typed body 驗證，非 500）。"""
    uid, cid, pid = await _mk_pc()
    try:
        r = await client.post(
            f"/tenants/{TID}/sops/drafts",
            json={"source_case_id": pid, "source_type": "problem_card",
                  "model_version": "m@1"},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())})
        assert r.status_code == 422, r.text
    finally:
        await _cleanup(uid, cid, pid)
