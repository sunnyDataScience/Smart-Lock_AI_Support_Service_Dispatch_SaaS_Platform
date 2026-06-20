"""CR-0079 / TI-A10-02 — 高風險 SOP 雙審 + 不可篡改 ledger（合約 4.4d 紅線）。

雙審 distinct：家族覆核者 ≠ 初審 admin（Knowledge Owner ≠ domain expert，四眼）。
不可篡改 ledger：family_reviews hash chain，篡改可偵測。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import family_review_service as fr

TID = "00000000-0000-0000-0000-000000000001"
ADMIN = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
EXPERT = "d1893a7f-1c2e-4a6b-9e4d-2f5b8c6a1e02"


async def _seed_approved_sop(admin_reviewer: str) -> str:
    sid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO sop_drafts (id, tenant_id, title, steps, status, reviewed_by, reviewed_at) "
        "VALUES (%s::uuid, %s::uuid, '高風險 SOP', '[]'::jsonb, 'approved', %s::uuid, NOW())",
        (sid, TID, admin_reviewer))
    return sid


async def _cleanup(sid):
    await db_module._conn.execute("DELETE FROM family_reviews WHERE sop_draft_id=%s::uuid", (sid,))
    await db_module._conn.execute("DELETE FROM sop_drafts WHERE id=%s::uuid", (sid,))


# ── 雙審四眼：家族覆核者 == 初審 admin → 403 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_dual_review_four_eyes_blocks_same_reviewer():
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop(ADMIN)
    try:
        with pytest.raises(ApiError) as e:
            await fr.create_review(tenant_id=TID, sop_draft_id=sid, action="approved",
                                   comment="自審", reviewer_id=ADMIN)   # 同初審人
        assert e.value.error_code == "SOD_VIOLATION" and e.value.status_code == 403
    finally:
        await _cleanup(sid)


# ── 雙審 distinct → 成功 + ledger entry_hash 落 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_dual_review_distinct_succeeds_and_chains():
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop(ADMIN)
    try:
        out = await fr.create_review(tenant_id=TID, sop_draft_id=sid, action="approved",
                                     comment="覆核通過", reviewer_id=EXPERT)
        assert out["action"] == "approved"
        cur = await db_module._conn.execute(
            "SELECT entry_hash FROM family_reviews WHERE sop_draft_id=%s::uuid", (sid,))
        h = (await cur.fetchone())[0]
        assert h and len(h) == 64        # sha256 ledger hash 落了
    finally:
        await _cleanup(sid)


# ── 不可篡改 ledger：篡改 action → verify 偵測 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_ledger_tamper_detected():
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop(ADMIN)
    try:
        await fr.create_review(tenant_id=TID, sop_draft_id=sid, action="approved",
                               comment="原始", reviewer_id=EXPERT)
        cur = await db_module._conn.execute(
            "SELECT id, sop_draft_id, action, reviewer_id, comment, prev_hash, entry_hash "
            "FROM family_reviews WHERE sop_draft_id=%s::uuid", (sid,))
        r = await cur.fetchone()
        # 重算一致（篡改前）
        content = fr._fr_canonical(str(r[1]), r[2], str(r[3]), r[4])
        assert fr._fr_entry_hash(r[5] or fr._FR_GENESIS, content) == r[6]
        # 篡改 action（approved→rejected），entry_hash 不動 → 重算對不上
        await db_module._conn.execute(
            "UPDATE family_reviews SET action='rejected' WHERE id=%s::uuid", (r[0],))
        cur2 = await db_module._conn.execute(
            "SELECT sop_draft_id, action, reviewer_id, comment, prev_hash, entry_hash "
            "FROM family_reviews WHERE id=%s::uuid", (r[0],))
        r2 = await cur2.fetchone()
        content2 = fr._fr_canonical(str(r2[0]), r2[1], str(r2[2]), r2[3])
        assert fr._fr_entry_hash(r2[4] or fr._FR_GENESIS, content2) != r2[5]   # 偵測到篡改
    finally:
        await _cleanup(sid)
