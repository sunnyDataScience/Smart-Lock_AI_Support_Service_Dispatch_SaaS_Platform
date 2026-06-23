"""CR-0096：同一 LINE 客人的不同問題各自獨立成卡。

根因：problem_cards.conversation_id 全唯一 + LINE 同用戶永遠同 conversation
      → 一個客人一輩子只有一張卡，第二個問題只能 append 進舊卡。
修法（業主裁決方案 A）：converted_at 標記已轉工單 + 部分唯一索引（同 conversation
      同時只一張 active 卡）。舊卡「已轉工單 或 已結案」→ 新問題開新卡；仍 active → append。
"""
from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import problem_card_service as pcs

TID = "00000000-0000-0000-0000-000000000001"


async def _new_line_uid() -> str:
    await db_module._ensure_conn()
    return "Utest-" + uuid.uuid4().hex[:12]


async def _cleanup(line_uid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM problem_cards WHERE conversation_id IN "
        "(SELECT c.id FROM conversations c JOIN users u ON c.user_id=u.id WHERE u.line_user_id=%s)",
        (line_uid,),
    )
    await db_module._conn.execute(
        "DELETE FROM conversations WHERE user_id IN (SELECT id FROM users WHERE line_user_id=%s)",
        (line_uid,),
    )
    await db_module._conn.execute("DELETE FROM users WHERE line_user_id=%s", (line_uid,))


async def _escalate(line_uid: str, text: str) -> dict:
    return await pcs.escalation_to_draft_pc(
        tenant_id=TID,
        line_user_id=line_uid,
        session_id=f"{TID}:{line_uid}",
        reason=text,
        facts_snapshot={"user_input_excerpt": text},
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_second_issue_appends_while_card_active():
    """舊卡仍 active（未轉工單/結案）→ 第二個問題併進同一張卡。"""
    line_uid = await _new_line_uid()
    try:
        r1 = await _escalate(line_uid, "門鎖打不開")
        assert r1["created"] is True
        r2 = await _escalate(line_uid, "電池也沒電")
        assert r2["created"] is False  # 沒建新卡
        assert r2["problem_card_id"] == r1["problem_card_id"]  # 併進同一張
    finally:
        await _cleanup(line_uid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_new_issue_after_converted_opens_new_card():
    """舊卡已轉工單（converted_at set）→ 新問題開新卡（同 conversation）。"""
    line_uid = await _new_line_uid()
    try:
        r1 = await _escalate(line_uid, "門鎖打不開")
        pc1, conv_id = r1["problem_card_id"], r1["conversation_id"]
        # 模擬轉工單（等同 work_order_service.create_from_problem_card 的 converted_at 標記）
        await db_module._conn.execute(
            "UPDATE problem_cards SET converted_at = NOW() WHERE id = %s::uuid", (pc1,)
        )
        r2 = await _escalate(line_uid, "另一個鎖要報修")
        assert r2["created"] is True  # 開了新卡
        assert r2["problem_card_id"] != pc1  # 不同卡
        assert r2["conversation_id"] == conv_id  # 同一 conversation
    finally:
        await _cleanup(line_uid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_new_issue_after_resolved_opens_new_card():
    """舊卡已結案（status=resolved）→ 新問題開新卡。"""
    line_uid = await _new_line_uid()
    try:
        r1 = await _escalate(line_uid, "問題一")
        pc1 = r1["problem_card_id"]
        await db_module._conn.execute(
            "UPDATE problem_cards SET status='resolved' WHERE id = %s::uuid", (pc1,)
        )
        r2 = await _escalate(line_uid, "問題二")
        assert r2["created"] is True
        assert r2["problem_card_id"] != pc1
    finally:
        await _cleanup(line_uid)
