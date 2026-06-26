"""CR-0022 / ADR-0112 — agent escalation → AI 草擬問題卡（HITL）測試。

涵蓋：
- require_internal_token 認證邊界（503/401）— 不需 DB。
- happy path：escalation → draft PC（source=ai_line、status=draft、ai_missing_fields）。
- 去重：同 session 再 escalation → 更新既有卡（created=False、同 conversation/pc）。
- charter lock：AI 路徑建出的卡為 'draft'（未 confirmed/未轉工單）— AI 不可自轉。
- source filter：list_cards 可篩 source=ai_line（service 層，免 JWT）。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

INGEST_PATH = "/api/v1/internal/escalations/ingest"
_TOKEN = "test-internal-token-cr0022"
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _body() -> dict:
    uid = f"Uesc-{uuid.uuid4().hex[:10]}"
    return {
        "tenant_id": DEFAULT_TENANT_ID,
        "line_user_id": uid,
        "session_id": f"{DEFAULT_TENANT_ID}:{uid}",
        "reason": "客人要求真人協助處理電子鎖故障",
        "is_explicit": True,
        "facts_snapshot": {"user_input_excerpt": "我的 Yale 鎖打不開，想找人來修"},
    }


@pytest_asyncio.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --------------------------- 認證邊界（無需 DB）---------------------------


@pytest.mark.asyncio
async def test_escalation_token_not_configured_503(client, monkeypatch):
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    resp = await client.post(INGEST_PATH, json=_body(), headers={"X-Internal-Token": "x"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_escalation_wrong_token_401(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(INGEST_PATH, json=_body(), headers={"X-Internal-Token": "nope"})
    assert resp.status_code == 401


# --------------------------- happy path（需 dev DB）---------------------------


@pytest.mark.asyncio
async def test_escalation_creates_draft_pc(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(INGEST_PATH, json=_body(), headers={"X-Internal-Token": _TOKEN})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] is True
    card = data["card"]
    # AI 草擬：source=ai_line、status=draft（DB incomplete）、待補欄位有 hint
    assert card["source"] == "ai_line"
    assert card["status"] == "draft"
    assert "brand" in (card["ai_missing_fields"] or [])
    assert "location" in (card["ai_missing_fields"] or [])


@pytest.mark.asyncio
async def test_escalation_dedup_same_session(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    r1 = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert r1.status_code == 200
    d1 = r1.json()["data"]
    assert d1["created"] is True

    # 同 session 再 escalation → 更新既有卡，不重建
    body2 = {**body, "reason": "客人再次催促"}
    r2 = await client.post(INGEST_PATH, json=body2, headers={"X-Internal-Token": _TOKEN})
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["created"] is False
    assert d2["problem_card_id"] == d1["problem_card_id"]
    assert d2["conversation_id"] == d1["conversation_id"]


@pytest.mark.asyncio
async def test_charter_ai_draft_not_confirmed(client, monkeypatch):
    """charter lock：AI 路徑只建 draft，狀態不得是 confirmed（confirm/convert 必須人類）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(INGEST_PATH, json=_body(), headers={"X-Internal-Token": _TOKEN})
    assert resp.status_code == 200
    card = resp.json()["data"]["card"]
    assert card["status"] == "draft"
    assert card["status"] != "confirmed"


# --------------------------- 對話狀態翻轉（F-018 handover 啟用前提）---------------------------


@pytest.mark.asyncio
async def test_escalation_flips_conversation_to_waiting_human(client, monkeypatch):
    """escalation → 對話狀態必須翻成 escalated（API: waiting_human），

    否則對話管理 HandoverComposer 永遠唯讀、send_message 回 409，客服無法回 LINE。
    """
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(INGEST_PATH, json=_body(), headers={"X-Internal-Token": _TOKEN})
    assert resp.status_code == 200, resp.text
    conv_id = resp.json()["data"]["conversation_id"]

    from services import conversation_service

    conv = await conversation_service.get_conversation(
        tenant_id=DEFAULT_TENANT_ID, conv_id=conv_id
    )
    # _coerce_status：DB 'escalated' → API 'waiting_human'
    assert conv["status"] == "waiting_human", conv


@pytest.mark.asyncio
async def test_re_escalation_keeps_waiting_human(client, monkeypatch):
    """同 session 再次 escalation（dedup 路徑）仍維持 escalated。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    r1 = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert r1.status_code == 200
    conv_id = r1.json()["data"]["conversation_id"]

    r2 = await client.post(
        INGEST_PATH, json={**body, "reason": "再次催促"}, headers={"X-Internal-Token": _TOKEN}
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["created"] is False

    from services import conversation_service

    conv = await conversation_service.get_conversation(
        tenant_id=DEFAULT_TENANT_ID, conv_id=conv_id
    )
    assert conv["status"] == "waiting_human", conv


# --------------------------- CR-0102 電話回填 users.phone（轉工單自動帶 customer_phone）---------------------------


@pytest.mark.asyncio
async def test_escalation_backfills_user_phone_when_empty(client, monkeypatch):
    """CR-0102：facts_snapshot 帶手機 → 正規化後寫進該對話 user 的 users.phone（空白時填）。
    convert（create_from_problem_card）既有邏輯讀 users.phone → 轉工單時 customer_phone 自動填上。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    body["facts_snapshot"] = {**body["facts_snapshot"], "phone": "0922-371-211"}
    resp = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert resp.status_code == 200, resp.text
    conv_id = resp.json()["data"]["conversation_id"]

    import core.db as db_module

    cur = await db_module._conn.execute(
        "SELECT u.phone FROM users u JOIN conversations c ON c.user_id = u.id "
        "WHERE c.id = %s::uuid",
        (conv_id,),
    )
    row = await cur.fetchone()
    assert row is not None
    assert row[0] == "0922371211"  # 分隔符正規化後寫入


@pytest.mark.asyncio
async def test_escalation_does_not_overwrite_existing_phone(client, monkeypatch):
    """CR-0102：users.phone 已有值 → 不被新偵測到的電話覆蓋（fill-if-empty，護住客服手動值）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    body["facts_snapshot"] = {**body["facts_snapshot"], "phone": "0911111111"}
    r1 = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert r1.status_code == 200
    conv_id = r1.json()["data"]["conversation_id"]

    # 同 session 再 escalation 帶不同電話 → 不覆蓋首次寫入
    body2 = {**body, "facts_snapshot": {**body["facts_snapshot"], "phone": "0922222222"}}
    r2 = await client.post(INGEST_PATH, json=body2, headers={"X-Internal-Token": _TOKEN})
    assert r2.status_code == 200

    import core.db as db_module

    cur = await db_module._conn.execute(
        "SELECT u.phone FROM users u JOIN conversations c ON c.user_id = u.id "
        "WHERE c.id = %s::uuid",
        (conv_id,),
    )
    row = await cur.fetchone()
    assert row[0] == "0911111111"  # 維持首次寫入，第二次不覆蓋


@pytest.mark.asyncio
async def test_escalation_ignores_non_mobile_phone(client, monkeypatch):
    """CR-0102：非台灣手機（市話/雜訊）→ 不寫入 users.phone（API 端正規化擋）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    body["facts_snapshot"] = {**body["facts_snapshot"], "phone": "02-12345678"}
    resp = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert resp.status_code == 200
    conv_id = resp.json()["data"]["conversation_id"]

    import core.db as db_module

    cur = await db_module._conn.execute(
        "SELECT u.phone FROM users u JOIN conversations c ON c.user_id = u.id "
        "WHERE c.id = %s::uuid",
        (conv_id,),
    )
    row = await cur.fetchone()
    assert not row[0]  # 市話未通過手機正規化 → 不寫（NULL 或空）


# --------------------------- source filter（service 層，免 JWT）---------------------------


@pytest.mark.asyncio
async def test_list_cards_source_filter(client, monkeypatch):
    """先 ingest 一張 ai_line 草擬卡，再用 list_cards(source='ai_line') 應撈得到。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body()
    r = await client.post(INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN})
    assert r.status_code == 200
    pc_id = r.json()["data"]["problem_card_id"]

    from services import problem_card_service

    page = await problem_card_service.list_cards(
        tenant_id=DEFAULT_TENANT_ID, cursor=None, limit=100, source="ai_line"
    )
    ids = {c["id"] for c in page["items"]}
    assert pc_id in ids
    assert all(c["source"] == "ai_line" for c in page["items"])
