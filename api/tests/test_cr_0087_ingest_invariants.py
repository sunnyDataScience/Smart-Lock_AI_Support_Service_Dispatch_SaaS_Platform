"""CR-0087 / TI-M01-03 + TI-SYNC-01 — ingest message_count 多輪累加 + no-silent-fail 不變式。

補既有 test_internal_ingest.py 的 gap：message_count 多輪正確累加（非僅單輪）+ 空 turn
不灌數（no silent over-count）。
"""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

INGEST_PATH = "/api/v1/internal/conversations/ingest"
_TOKEN = "test-internal-token-abc123"
TID = "00000000-0000-0000-0000-000000000001"


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _body(session_id, user_text="鎖打不開", assistant_text="請問品牌型號？"):
    return {"tenant_id": TID, "line_user_id": session_id.split(":")[-1],
            "session_id": session_id, "user_text": user_text, "assistant_text": assistant_text}


async def _conv_message_count(conv_id):
    import core.db as db_module
    cur = await db_module._conn.execute(
        "SELECT message_count FROM conversations WHERE id=%s::uuid", (conv_id,))
    row = await cur.fetchone()
    return row[0] if row else None


@pytest.mark.component
@pytest.mark.asyncio
async def test_message_count_accumulates_across_turns(client, monkeypatch):
    """3 輪 ingest（各 user+assistant=2 則）→ message_count 累加到 6（非停在 2）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    sid = f"{TID}:Uacc-{uuid.uuid4().hex[:10]}"
    import core.db as db_module
    conv_id = None
    try:
        for i in range(3):
            resp = await client.post(INGEST_PATH, json=_body(sid, f"訊息{i}", f"回覆{i}"),
                                     headers={"X-Internal-Token": _TOKEN})
            assert resp.status_code == 200, resp.text
            conv_id = resp.json()["data"]["conversation_id"]
        assert await db_module._ensure_conn()
        # 3 輪 × 2 則 = 6（累加正確，非單輪覆蓋）
        assert await _conv_message_count(conv_id) == 6
    finally:
        if conv_id:
            cur = await db_module._conn.execute(
                "SELECT user_id FROM conversations WHERE id=%s::uuid", (conv_id,))
            r = await cur.fetchone()
            if r:
                await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (r[0],))


@pytest.mark.component
@pytest.mark.asyncio
async def test_empty_assistant_does_not_overcount(client, monkeypatch):
    """SYNC-01 no-silent-fail：空 assistant turn 只計 user 1 則（不灌空訊息數）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    sid = f"{TID}:Uempty-{uuid.uuid4().hex[:10]}"
    import core.db as db_module
    conv_id = None
    try:
        r1 = await client.post(INGEST_PATH, json=_body(sid, "只有客人說話", ""),
                               headers={"X-Internal-Token": _TOKEN})
        assert r1.status_code == 200
        assert r1.json()["data"]["messages_appended"] == 1   # 空 assistant 不寫
        conv_id = r1.json()["data"]["conversation_id"]
        assert await db_module._ensure_conn()
        assert await _conv_message_count(conv_id) == 1        # count 與實寫一致（no over-count）
    finally:
        if conv_id:
            cur = await db_module._conn.execute(
                "SELECT user_id FROM conversations WHERE id=%s::uuid", (conv_id,))
            r = await cur.fetchone()
            if r:
                await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (r[0],))
