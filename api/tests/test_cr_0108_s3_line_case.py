"""CR-0108 S3 — LINE 進線 escalation 自動帶 Case 測試。

  S3-1 LINE escalation 建草擬卡 → problem_cards.case_id 已連 + intake_case(source_channel=line) 存在
  S3-2 同 session 再 escalation（併入既有卡）→ 仍同一張 Case（不重複建）
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID


async def _escalate(line_user_id: str, reason: str) -> dict:
    from services import problem_card_service

    return await problem_card_service.escalation_to_draft_pc(
        tenant_id=DEFAULT_TENANT_ID,
        line_user_id=line_user_id,
        session_id=f"{DEFAULT_TENANT_ID}:{line_user_id}",
        reason=reason,
        is_explicit=True,
        facts_snapshot={"user_input_excerpt": reason},
    )


async def _case_id_of_pc(pc_id: str):
    import core.db as db_module

    cur = await db_module._conn.execute(
        "SELECT case_id FROM problem_cards WHERE id = %s::uuid", (pc_id,))
    row = await cur.fetchone()
    return str(row[0]) if row and row[0] else None


async def _cleanup(line_user_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    # conversation → problem_cards → intake_case 連鎖清理
    cur = await db_module._conn.execute(
        "SELECT id FROM conversations WHERE session_id = %s", (f"{DEFAULT_TENANT_ID}:{line_user_id}",))
    rows = await cur.fetchall()
    for (conv_id,) in rows:
        pcur = await db_module._conn.execute(
            "SELECT id, case_id FROM problem_cards WHERE conversation_id = %s::uuid", (conv_id,))
        for pc_id, case_id in await pcur.fetchall():
            if case_id:
                await db_module._conn.execute(
                    "DELETE FROM saas.intake_case WHERE id = %s::uuid", (case_id,))
            await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,))
        await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (conv_id,))
    await db_module._conn.execute("DELETE FROM users WHERE line_user_id = %s", (line_user_id,))


@pytest.mark.asyncio
@pytest.mark.component
async def test_s3_line_escalation_creates_linked_case(client):
    """S3-1：LINE escalation → 卡連 case_id + intake_case source_channel=line。"""
    import core.db as db_module

    uid = f"Us3-{uuid.uuid4().hex[:10]}"
    try:
        res = await _escalate(uid, "Yale 電子鎖打不開 想找人修")
        assert res["created"] is True
        pc_id = res["problem_card_id"]

        case_id = await _case_id_of_pc(pc_id)
        assert case_id is not None, "problem_card.case_id 應已連上 Case"

        cur = await db_module._conn.execute(
            "SELECT source_channel, customer_line_id, status FROM saas.intake_case WHERE id = %s::uuid",
            (case_id,))
        row = await cur.fetchone()
        assert row is not None
        assert row[0] == "line"
        assert row[1] == uid  # 客戶 LINE ID 帶入
        assert row[2] == "open"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
@pytest.mark.component
async def test_s3_same_session_reuses_case(client):
    """S3-2：同 session 再 escalation（併入既有卡）→ 仍同一張 Case，不重複建。"""
    uid = f"Us3-{uuid.uuid4().hex[:10]}"
    try:
        r1 = await _escalate(uid, "門鎖卡住")
        pc1 = r1["problem_card_id"]
        case1 = await _case_id_of_pc(pc1)
        assert case1 is not None

        r2 = await _escalate(uid, "客人再次催促")
        assert r2["problem_card_id"] == pc1  # 併入同卡
        case2 = await _case_id_of_pc(pc1)
        assert case2 == case1  # 仍同一張 Case（冪等，未重建）
    finally:
        await _cleanup(uid)
