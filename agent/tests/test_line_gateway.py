"""LINE 通道測試 — 離線。webhook 路徑用真實簽章 + patch 掉 LINE reply API。"""

import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from lockcore.channels.line_gateway import handle_text_turn, load_dotenv, resolve_identity


def test_resolve_identity_line_uses_userid():
    assert resolve_identity("line", "U1234", "locksmart") == ("locksmart", "U1234")


def test_load_dotenv_parses_quoted(tmp_path, monkeypatch):
    monkeypatch.delenv("FOO_X", raising=False)
    f = tmp_path / ".env"
    f.write_text('# comment\nFOO_X="bar baz"\nEMPTY=\n', encoding="utf-8")
    loaded = load_dotenv(f)
    assert loaded["FOO_X"] == "bar baz"
    import os
    assert os.environ["FOO_X"] == "bar baz"


def test_load_dotenv_missing_file_ok(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") == {}


class _FakeOut:
    def __init__(self, content):
        self.content = content


class _FakeLoop:
    def __init__(self, reply):
        self._reply = reply
        self.seen: dict = {}

    async def _process_message(self, msg, session_key=None):
        self.seen = {"sender_id": msg.sender_id, "content": msg.content, "session_key": session_key}
        return _FakeOut(self._reply)


def test_handle_text_turn_routes_and_returns():
    loop = _FakeLoop("您家的鎖是 Dormakaba AS701")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "我的鎖什麼型號"))
    assert out == "您家的鎖是 Dormakaba AS701"
    assert loop.seen["sender_id"] == "U1"
    assert loop.seen["session_key"] == "locksmart:U1"


def test_handle_text_turn_blank_skips():
    loop = _FakeLoop("x")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "   "))
    assert out == ""
    assert loop.seen == {}   # 空訊息不進 loop


def test_handle_text_turn_truncates_long_reply():
    loop = _FakeLoop("一" * 6000)
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "問題"))
    assert len(out) == 4900


def test_handle_text_turn_masks_internal_error():
    """LLM/provider 失敗時的 [litellm error] 不可外洩給客人,改友善話術。"""
    loop = _FakeLoop("[litellm error] litellm.BadRequestError: ...403 billing...")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "你好"))
    assert "litellm" not in out
    assert "error" not in out.lower()
    assert "專員" in out   # 友善 fallback


def test_handle_text_turn_empty_reply_returns_empty():
    loop = _FakeLoop("   ")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "你好"))
    assert out == ""


# ---- webhook 路徑(需 line-bot-sdk + aiohttp test server)----

pytest.importorskip("linebot")
aiohttp_test = pytest.importorskip("aiohttp.test_utils")


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _webhook_body(user_id: str, text: str, reply_token: str = "rt1") -> bytes:
    payload = {
        "destination": "xxx",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1,
                "webhookEventId": "evt1",
                "deliveryContext": {"isRedelivery": False},
                "source": {"type": "user", "userId": user_id},
                "replyToken": reply_token,
                "message": {"type": "text", "id": "m1", "text": text, "quoteToken": "q1"},
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


def test_webhook_valid_signature_invokes_loop_and_replies(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    from lockcore.channels import line_gateway

    secret = "testsecret"
    loop = _FakeLoop("好的,已為您記下 🔐")

    replied: dict = {}

    async def _fake_reply(self, req, **kw):
        replied["text"] = req.messages[0].text
        replied["token"] = req.reply_token

    # 不要真的打 LINE API
    from linebot.v3.messaging import AsyncMessagingApi
    monkeypatch.setattr(AsyncMessagingApi, "reply_message", _fake_reply, raising=True)

    app = line_gateway.build_webapp(loop, "locksmart", secret, "dummy-token")

    async def run():
        async with TestClient(TestServer(app)) as client:
            body = _webhook_body("Uabc", "我的鎖是 Kaadas K9")
            sig = _sign(secret, body)
            resp = await client.post("/callback", data=body, headers={"X-Line-Signature": sig})
            assert resp.status == 200
            # bad signature → 400
            bad = await client.post("/callback", data=body, headers={"X-Line-Signature": "nope"})
            assert bad.status == 400

    asyncio.run(run())

    assert loop.seen["sender_id"] == "Uabc"
    assert loop.seen["content"] == "我的鎖是 Kaadas K9"
    assert replied["text"] == "好的,已為您記下 🔐"
    assert replied["token"] == "rt1"
