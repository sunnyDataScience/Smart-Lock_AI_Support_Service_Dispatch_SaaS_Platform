"""CR-0164 C：SOP adopt 家族覆核硬 gate（合約 4.4d 紅線，衝突①裁定＝硬 gate）。

adopt_draft（approved→published+case_entry）原全程不查 family_reviews → 未覆核即可
發布進 KB/RAG（TC-COMPLIANCE-05 P0 假綠）。修：adopt 前須有 action='approved' 的
家族覆核，缺 → 425 FAMILY_REVIEW_REQUIRED。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import family_review_service as fr
from services import sop_draft_service as svc

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
ADMIN = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
EXPERT = "d1893a7f-1c2e-4a6b-9e4d-2f5b8c6a1e02"


async def _seed_approved_sop() -> str:
    sid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO sop_drafts (id, tenant_id, title, steps, status, reviewed_by, reviewed_at) "
        "VALUES (%s::uuid, %s::uuid, 'CR-0164 gate SOP', '[]'::jsonb, 'approved', %s::uuid, NOW())",
        (sid, TID, ADMIN))
    return sid


async def _cleanup(sid: str) -> None:
    # case_entries 無 draft_id 欄（靠 source/approved_by 關聯）→ 以 title 清（本測試唯一）
    await db_module._conn.execute(
        "DELETE FROM case_entries WHERE title='CR-0164 gate SOP' AND source='sop_approved'")
    await db_module._conn.execute("DELETE FROM family_reviews WHERE sop_draft_id=%s::uuid", (sid,))
    await db_module._conn.execute("DELETE FROM sop_drafts WHERE id=%s::uuid", (sid,))


@pytest.mark.asyncio
async def test_adopt_without_family_review_425():
    """approved 但無家族覆核 → adopt 425 FAMILY_REVIEW_REQUIRED（原：直接 published）。"""
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop()
    try:
        with pytest.raises(ApiError) as exc:
            await svc.adopt_draft(tenant_id=TID, draft_id=sid, target_case_id=None, approver_id=ADMIN)
        assert exc.value.status_code == 425
        assert exc.value.error_code == "FAMILY_REVIEW_REQUIRED"
        # 未 published（仍 approved）
        st = await (await db_module._conn.execute(
            "SELECT status FROM sop_drafts WHERE id=%s::uuid", (sid,))).fetchone()
        assert st[0] == "approved"
    finally:
        await _cleanup(sid)


@pytest.mark.asyncio
async def test_adopt_rejected_family_review_still_425():
    """有家族覆核但 action='rejected' → 仍 425（不可只判存在）。"""
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop()
    try:
        # 直接落一筆 rejected family_review（rejected 不退 status）
        await db_module._conn.execute(
            "INSERT INTO family_reviews (tenant_id, sop_draft_id, action, reviewer_id) "
            "VALUES (%s::uuid, %s::uuid, 'rejected', %s::uuid)", (TID, sid, EXPERT))
        with pytest.raises(ApiError) as exc:
            await svc.adopt_draft(tenant_id=TID, draft_id=sid, target_case_id=None, approver_id=ADMIN)
        assert exc.value.status_code == 425
    finally:
        await _cleanup(sid)


@pytest.mark.asyncio
async def test_adopt_with_approved_family_review_succeeds():
    """有 action='approved' 家族覆核（四眼 reviewer≠初審 admin）→ adopt 成功 published。"""
    assert await db_module._ensure_conn()
    sid = await _seed_approved_sop()
    try:
        await fr.create_review(
            tenant_id=TID, sop_draft_id=sid, action="approved",
            comment="家族覆核通過", reviewer_id=EXPERT)
        case = await svc.adopt_draft(
            tenant_id=TID, draft_id=sid, target_case_id=None, approver_id=ADMIN)
        assert case.get("id"), "adopt 應建 case_entry"
        st = await (await db_module._conn.execute(
            "SELECT status FROM sop_drafts WHERE id=%s::uuid", (sid,))).fetchone()
        assert st[0] == "published"
    finally:
        await _cleanup(sid)
