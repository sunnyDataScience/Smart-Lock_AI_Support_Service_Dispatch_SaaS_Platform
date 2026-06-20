"""CR-0065 測試計畫覆蓋 Batch 3（M03 ProblemCard 缺功能補實作+測試）。

- TI-M03-06：ProblemCard idempotency key（sha256(conv_id+症狀+brand) + 24h dedup）
- TI-M03-07：ProblemCard media_urls append-only（更新不覆蓋，聯集去重保序）
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module

TID = "00000000-0000-0000-0000-000000000001"


# ── TI-M03-06 冪等鍵純函式 ──
@pytest.mark.unit
def test_idempotency_key_deterministic():
    from services.problem_card_service import compute_pc_idempotency_key
    c = str(uuid.uuid4())
    k1 = compute_pc_idempotency_key(c, "Yale 鎖打不開", "Yale")
    k2 = compute_pc_idempotency_key(c, "  Yale 鎖打不開 ", "Yale ")  # 前後空白正規化
    assert k1 == k2 and len(k1) == 64                # sha256 hex
    assert k1 != compute_pc_idempotency_key(c, "電池沒電", "Yale")   # 不同症狀
    assert k1 != compute_pc_idempotency_key(c, "Yale 鎖打不開", "Philips")  # 不同品牌
    assert k1 != compute_pc_idempotency_key(str(uuid.uuid4()), "Yale 鎖打不開", "Yale")  # 不同對話


async def _cleanup_user_by_session(session_id: str):
    """經 conversation.session_id 找 user 刪除（cascade conversations + problem_cards）。"""
    cur = await db_module._conn.execute(
        "SELECT user_id FROM conversations WHERE session_id = %s", (session_id,))
    rows = await cur.fetchall()
    for r in rows:
        await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (r[0],))


# ── TI-M03-06 escalation 24h dedup（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_escalation_idempotency_dedup():
    assert await db_module._ensure_conn()
    from services import problem_card_service as pcs
    uid = f"Uidem-{uuid.uuid4().hex[:10]}"
    session_id = f"{TID}:{uid}"
    try:
        r1 = await pcs.escalation_to_draft_pc(
            tenant_id=TID, line_user_id=uid, session_id=session_id,
            reason="客人要求真人 Yale 鎖故障",
            facts_snapshot={"user_input_excerpt": "我的 Yale 鎖打不開"})
        assert r1["created"] is True
        pc_id = r1["problem_card_id"]
        # 第二次同 turn 重送 → 命中冪等鍵/對話去重，不重建
        r2 = await pcs.escalation_to_draft_pc(
            tenant_id=TID, line_user_id=uid, session_id=session_id,
            reason="客人要求真人 Yale 鎖故障",
            facts_snapshot={"user_input_excerpt": "我的 Yale 鎖打不開"})
        assert r2["created"] is False
        assert r2["problem_card_id"] == pc_id        # 回既有同卡
        # DB 端冪等鍵已落庫（64 hex）
        cur = await db_module._conn.execute(
            "SELECT idempotency_key FROM problem_cards WHERE id = %s::uuid", (pc_id,))
        key = (await cur.fetchone())[0]
        assert key and len(key) == 64
    finally:
        await _cleanup_user_by_session(session_id)


# ── TI-M03-07 media_urls append-only（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_media_urls_append_only():
    assert await db_module._ensure_conn()
    from services import problem_card_service as pcs
    uid = f"Umedia-{uuid.uuid4().hex[:10]}"
    session_id = f"{TID}:{uid}"
    try:
        r = await pcs.escalation_to_draft_pc(
            tenant_id=TID, line_user_id=uid, session_id=session_id,
            reason="鎖故障", facts_snapshot={"user_input_excerpt": "鎖故障"})
        pc_id = r["problem_card_id"]
        # 第一批媒體
        await pcs.update_card(tenant_id=TID, pc_id=pc_id,
                              media_urls=["/api/v1/media/a", "/api/v1/media/b"])
        # 第二批：含一個重複(b) + 一個新(c) → 應聯集去重保序為 [a,b,c]，不覆蓋
        out = await pcs.update_card(tenant_id=TID, pc_id=pc_id,
                                    media_urls=["/api/v1/media/b", "/api/v1/media/c"])
        assert out["media_urls"] == ["/api/v1/media/a", "/api/v1/media/b", "/api/v1/media/c"]
    finally:
        await _cleanup_user_by_session(session_id)
