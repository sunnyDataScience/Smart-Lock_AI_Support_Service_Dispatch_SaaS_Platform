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
