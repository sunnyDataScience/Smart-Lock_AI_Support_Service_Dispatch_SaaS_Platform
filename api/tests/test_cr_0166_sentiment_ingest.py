"""CR-0166 R2：負面情緒隨對話 ingest → sentiment_alerts 告警（K3'/合約 4.4a）。"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import conversation_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


async def _cleanup(line_uid: str) -> None:
    await db_module._ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT id FROM conversations WHERE user_id IN "
        "(SELECT id FROM users WHERE line_user_id=%s)", (line_uid,))
    for (cid,) in await cur.fetchall():
        await db_module._conn.execute(
            "DELETE FROM sentiment_alerts WHERE conversation_id=%s::uuid", (cid,))
        await db_module._conn.execute("DELETE FROM messages WHERE conversation_id=%s::uuid", (cid,))
        await db_module._conn.execute("DELETE FROM conversations WHERE id=%s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE line_user_id=%s", (line_uid,))


@pytest.mark.asyncio
async def test_negative_sentiment_writes_alert():
    line_uid = f"Usent{uuid.uuid4().hex[:20]}"
    try:
        r = await conversation_service.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="你們爛透了我要投訴找律師", assistant_text="已為您轉接專員",
            sentiment_label="very_negative", sentiment_confidence=0.95,
            sentiment_keywords=["投訴", "律師"],
        )
        conv_id = r["conversation_id"]
        row = await (await db_module._conn.execute(
            "SELECT sentiment_label, confidence, detected_keywords, status "
            "FROM sentiment_alerts WHERE conversation_id=%s::uuid", (conv_id,))).fetchone()
        assert row is not None, "負面情緒應寫入 sentiment_alerts"
        assert row[0] == "very_negative"
        assert float(row[1]) == pytest.approx(0.95, abs=0.01)
        assert "投訴" in row[2]
        assert row[3] == "pending"
    finally:
        await _cleanup(line_uid)


@pytest.mark.asyncio
async def test_neutral_sentiment_no_alert():
    line_uid = f"Usent{uuid.uuid4().hex[:20]}"
    try:
        r = await conversation_service.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="請問可以換鎖嗎", assistant_text="可以的，請提供品牌型號",
            sentiment_label="neutral", sentiment_confidence=0.9,
        )
        conv_id = r["conversation_id"]
        cnt = await (await db_module._conn.execute(
            "SELECT count(*) FROM sentiment_alerts WHERE conversation_id=%s::uuid",
            (conv_id,))).fetchone()
        assert cnt[0] == 0, "中性情緒不應告警"
    finally:
        await _cleanup(line_uid)


@pytest.mark.asyncio
async def test_no_sentiment_field_no_alert():
    """未帶 sentiment（既有 caller 行為不變）→ 不告警。"""
    line_uid = f"Usent{uuid.uuid4().hex[:20]}"
    try:
        r = await conversation_service.ingest_turn(
            tenant_id=TID, line_user_id=line_uid, session_id=f"{TID}:{line_uid}",
            user_text="你好", assistant_text="您好",
        )
        conv_id = r["conversation_id"]
        cnt = await (await db_module._conn.execute(
            "SELECT count(*) FROM sentiment_alerts WHERE conversation_id=%s::uuid",
            (conv_id,))).fetchone()
        assert cnt[0] == 0
    finally:
        await _cleanup(line_uid)
