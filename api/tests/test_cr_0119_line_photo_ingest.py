"""CR-0119 — LINE 客人照片顯示於對話管理。

涵蓋：
- ingest 帶 media_base64/media_mime → 照片落 media_service（purpose=other），
  user 訊息 metadata.image_url → GET messages 回 media_url，且該 URL 可帶
  admin 憑證下載回原 bytes（tenant 隔離沿用既有 media 端點）。
- 壞 base64 → fail-soft：文字照寫、media_url 為 None（照片問題不弄丟對話）。
- 未帶 media（既有呼叫端）→ 行為完全不變（additive 回歸守門）。
- 只帶照片沒文字 → 自動補「[照片]」佔位，訊息仍寫得出來。
"""

from __future__ import annotations

import base64
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

INGEST_PATH = "/api/v1/internal/conversations/ingest"
_TOKEN = "test-internal-token-cr0119"
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _body(**overrides) -> dict:
    body = {
        "tenant_id": DEFAULT_TENANT_ID,
        "line_user_id": f"Utest-{uuid.uuid4().hex[:10]}",
        "session_id": f"{DEFAULT_TENANT_ID}:Utest-{uuid.uuid4().hex[:10]}",
        "user_text": "[照片]",
        "assistant_text": "收到您的照片，看起來是電池蓋的位置。",
    }
    body.update(overrides)
    return body


@pytest_asyncio.fixture
async def iclient():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _fetch_user_message(iclient, admin_headers, conv_id: str) -> dict:
    """讀回該對話最新 user 訊息（v2 tenant-scoped 端點，DESC）。"""
    resp = await iclient.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/messages",
        headers=admin_headers,
        params={"limit": 10},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    user_msgs = [m for m in items if m["role"] == "user"]
    assert user_msgs, f"對話 {conv_id} 應有 user 訊息"
    return user_msgs[0]


@pytest.mark.asyncio
async def test_ingest_photo_persists_and_media_downloadable(
    iclient, admin_headers, monkeypatch
):
    """帶照片 ingest → messages 回 media_url，URL 可下載回原 bytes。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body(
        media_base64=base64.b64encode(FAKE_PNG).decode("ascii"),
        media_mime="image/png",
    )
    resp = await iclient.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["messages_appended"] == 2
    conv_id = data["conversation_id"]

    msg = await _fetch_user_message(iclient, admin_headers, conv_id)
    assert msg["content"] == "[照片]"
    media_url = msg.get("media_url")
    assert media_url and media_url.startswith("/api/v1/media/"), msg

    # 該 URL 帶 admin 憑證可下載回原 bytes（tenant 隔離由既有端點把關）
    dl = await iclient.get(media_url, headers=admin_headers)
    assert dl.status_code == 200, dl.text
    assert dl.headers["content-type"] == "image/png"
    assert dl.content == FAKE_PNG


@pytest.mark.asyncio
async def test_ingest_bad_base64_failsoft_keeps_text(
    iclient, admin_headers, monkeypatch
):
    """壞 base64 → 照片略過（media_url None），文字訊息照寫（fail-soft）。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body(media_base64="!!!not-base64!!!", media_mime="image/png")
    resp = await iclient.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["messages_appended"] == 2

    msg = await _fetch_user_message(iclient, admin_headers, data["conversation_id"])
    assert msg["content"] == "[照片]"
    assert msg.get("media_url") in (None, "")


@pytest.mark.asyncio
async def test_ingest_without_media_unchanged(iclient, admin_headers, monkeypatch):
    """未帶 media 欄位（既有 gateway 呼叫端）→ 行為完全不變。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body(user_text="我的電子鎖沒電了")
    resp = await iclient.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["messages_appended"] == 2

    msg = await _fetch_user_message(iclient, admin_headers, data["conversation_id"])
    assert msg["content"] == "我的電子鎖沒電了"
    assert msg.get("media_url") in (None, "")


@pytest.mark.asyncio
async def test_ingest_photo_only_gets_placeholder_text(
    iclient, admin_headers, monkeypatch
):
    """只帶照片、user_text 空 → 服務端補「[照片]」佔位，訊息仍寫入。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", _TOKEN)
    body = _body(
        user_text="",
        media_base64=base64.b64encode(FAKE_PNG).decode("ascii"),
        media_mime="image/png",
    )
    resp = await iclient.post(
        INGEST_PATH, json=body, headers={"X-Internal-Token": _TOKEN}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["messages_appended"] == 2

    msg = await _fetch_user_message(iclient, admin_headers, data["conversation_id"])
    assert msg["content"] == "[照片]"
    assert (msg.get("media_url") or "").startswith("/api/v1/media/")
