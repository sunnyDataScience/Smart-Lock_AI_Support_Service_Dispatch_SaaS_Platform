"""CR-0133 對話三方全量存檔驗證（WBS 1.2.4 / BR-Conv-004 / FR-AGT-09）。

- ingest 一輪 → 客戶（line_user）＋ AI（ai）訊息各一、sender_role 入 metadata
- 接管期間：客戶訊息續入庫（ingest assistant 空）＋ 真人訊息（agent_human）同表同格式
- 三方齊備可依 sender_role 撈取（知識精煉閉環資料前提）
（agent 側「寫入失敗告警＋spool 補送」驗證在 agent/tests/test_line_gateway.py）
"""
from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import conversation_service as cs

TID = "00000000-0000-0000-0000-000000000001"

pytestmark = pytest.mark.component


async def _sender_roles(conv_id: str) -> list[str]:
    cur = await db_module._conn.execute(
        "SELECT metadata->>'sender_role' FROM messages "
        "WHERE conversation_id = %s::uuid ORDER BY created_at, id",
        (conv_id,),
    )
    return [r[0] for r in await cur.fetchall()]


async def _cleanup(line_uid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM messages WHERE conversation_id IN "
        "(SELECT c.id FROM conversations c JOIN users u ON c.user_id=u.id WHERE u.line_user_id=%s)",
        (line_uid,))
    await db_module._conn.execute(
        "DELETE FROM conversations WHERE user_id IN (SELECT id FROM users WHERE line_user_id=%s)",
        (line_uid,))
    await db_module._conn.execute("DELETE FROM users WHERE line_user_id=%s", (line_uid,))


@pytest.mark.asyncio
async def test_three_party_full_archive():
    """一輪 AI 對話 → 接管 → 接管期間客戶訊息 → 真人回覆：四筆全入庫、sender_role 正確。"""
    assert await db_module._ensure_conn()
    line_uid = f"U-arch-{uuid.uuid4().hex[:10]}"
    try:
        # 1) AI 輪（客戶+AI）
        out = await cs.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="門打不開", assistant_text="請先確認電池")
        conv_id = str(out["conversation_id"])
        assert out["messages_appended"] == 2

        # 2) 進接管（escalated）
        await db_module._conn.execute(
            "UPDATE conversations SET status='escalated' WHERE id=%s::uuid", (conv_id,))

        # 3) 接管期間客戶訊息（AI 暫停 → assistant_text 空，僅客戶側入庫）
        out = await cs.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="還是打不開", assistant_text="")
        assert out["messages_appended"] >= 1

        # 4) 真人小編回覆（同表同格式，sender_role=agent_human）
        await cs.send_message(
            tenant_id=TID, conv_id=conv_id,
            content="您好我是專員，馬上協助您", sender_user_id=str(uuid.uuid4()))

        roles = await _sender_roles(conv_id)
        assert roles[0] == "line_user" and roles[1] == "ai"
        assert "agent_human" in roles, roles
        # 接管期間客戶訊息零缺漏
        assert roles.count("line_user") == 2, roles
        # 三方 sender_role 值域（SRS {customer, ai_agent, human_agent} 之 code 映射，CR-0133 記載）
        assert set(roles) <= {"line_user", "ai", "agent_human", "system"}
    finally:
        await _cleanup(line_uid)


@pytest.mark.asyncio
async def test_sender_role_queryable_for_refinery():
    """精煉閉環前提：可按 sender_role 過濾撈訊息（BR-Conv-03/§5.5 第一類輸入）。"""
    assert await db_module._ensure_conn()
    line_uid = f"U-arch-{uuid.uuid4().hex[:10]}"
    try:
        out = await cs.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="WiFi 連不上", assistant_text="請重啟路由器")
        conv_id = str(out["conversation_id"])
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM messages WHERE conversation_id=%s::uuid "
            "AND metadata->>'sender_role' = 'ai'", (conv_id,))
        assert (await cur.fetchone())[0] == 1
    finally:
        await _cleanup(line_uid)
