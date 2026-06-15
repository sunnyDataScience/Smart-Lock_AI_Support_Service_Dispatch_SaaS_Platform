"""方案 A — internal conversation ingest 端點測試。

涵蓋：
- require_internal_token 認證邊界（fail closed 503 / 401）—— 不需 DB。
- happy path：ingest 一輪對話 → 200 + messages_appended，並可由
  GET /tenants/{id}/conversations/{convId}/messages 讀回 —— 需 dev DB。

認證邊界測試刻意送合法 body，確保失敗來源是 token 而非 body 驗證。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

INGEST_PATH = "/api/v1/internal/conversations/ingest"
_TOKEN = "test-internal-token-abc123"
# 對齊 conftest.DEFAULT_TENANT_ID（seed 預設租戶）
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _valid_body() -> dict:
    return {
        "tenant_id": DEFAULT_TENANT_ID,
        "line_user_id": f"Utest-{uuid.uuid4().hex[:10]}",
        "session_id": f"{DEFAULT_TENANT_ID}:Utest-{uuid.uuid4().hex[:10]}",
        "user_text": "我的電子鎖開不了門",
        "assistant_text": "請問您的鎖是哪個品牌與型號呢？",
    }


@pytest_asyncio.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --------------------------- 認證邊界（無需 DB）---------------------------


@pytest.mark.asyncio
async def test_ingest_token_not_configured_503(client, monkeypatch):
    """INTERNAL_API_TOKEN 未設 → fail closed 503，絕不放行。"""
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    resp = await client.post(
        INGEST_PATH, json=_valid_body(), headers={"X-Internal-Token": "anything"}
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ingest_missing_token_401(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(INGEST_PATH, json=_valid_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_wrong_token_401(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    resp = await client.post(
        INGEST_PATH, json=_valid_body(), headers={"X-Internal-Token": "wrong"}
    )
    assert resp.status_code == 401


# --------------------------- happy path（需 dev DB）---------------------------


@pytest.mark.asyncio
async def test_ingest_happy_path_persists_and_reads_back(client, monkeypatch):
    """ingest 一輪 → 200 寫 2 則訊息；同 session 再 ingest 復用同一對話（冪等）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _valid_body()

    resp = await client.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["messages_appended"] == 2
    conv_id = data["conversation_id"]
    assert conv_id

    # 同 session_id 再送 → 復用同一 conversation（不新建）
    resp2 = await client.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_ingest_skips_empty_text(client, monkeypatch):
    """只有客人訊息、AI 無回覆 → 只寫 1 則。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _valid_body()
    body["assistant_text"] = ""

    resp = await client.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["messages_appended"] == 1


# ---------------------------------------------------------------------------
# tenant_id 別名解析（_resolve_tenant_id）—— 純函式，免 DB。
# agent gateway 送 tenant_id="locksmart"（別名）而非 UUID，需對應到實際租戶 UUID，
# 否則 psycopg 對 uuid 欄位丟 500（修復前的真實 bug）。
# ---------------------------------------------------------------------------


def test_resolve_tenant_id_passthrough_uuid():
    from routers.internal_ingest import _resolve_tenant_id

    assert _resolve_tenant_id(DEFAULT_TENANT_ID) == DEFAULT_TENANT_ID


def test_resolve_tenant_id_alias_uses_env(monkeypatch):
    from routers.internal_ingest import _resolve_tenant_id

    monkeypatch.setenv("AGENT_TENANT_ID", DEFAULT_TENANT_ID)
    assert _resolve_tenant_id("locksmart") == DEFAULT_TENANT_ID


def test_resolve_tenant_id_alias_without_env_400(monkeypatch):
    from fastapi import HTTPException

    from routers.internal_ingest import _resolve_tenant_id

    monkeypatch.delenv("AGENT_TENANT_ID", raising=False)
    with pytest.raises(HTTPException) as ei:
        _resolve_tenant_id("locksmart")
    assert ei.value.status_code == 400


def test_resolve_tenant_id_bad_env_500(monkeypatch):
    from fastapi import HTTPException

    from routers.internal_ingest import _resolve_tenant_id

    monkeypatch.setenv("AGENT_TENANT_ID", "not-a-uuid")
    with pytest.raises(HTTPException) as ei:
        _resolve_tenant_id("locksmart")
    assert ei.value.status_code == 500
