"""CR-0017 Stage 5 — outbox worker unit tests (DB & LINE API mocked)。

驗證：
- _push_to_line: text / flex 兩型 message 都能轉 SDK obj
- _push_to_line: ApiException → (False, err)
- _push_to_line: LINE_CHANNEL_ACCESS_TOKEN 缺 → (False, ...)
- backoff escalation: 1→2→3→...→max_attempts 觸發 _mark_dead
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from realtime.line_push_outbox_worker import (
    LinePushOutboxWorker,
    _BACKOFF_SECONDS_BY_ATTEMPT,
)


@pytest.mark.asyncio
async def test_push_to_line_missing_token(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    w = LinePushOutboxWorker()
    ok, err = await w._push_to_line("U1", [{"type": "text", "text": "hi"}])
    assert ok is False
    assert "LINE_CHANNEL_ACCESS_TOKEN missing" in err


@pytest.mark.asyncio
async def test_push_to_line_text_message_path(monkeypatch):
    """text 訊息走 TextMessage 分支，呼到 push_message。"""
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")

    pushed = {}

    class FakeApi:
        async def push_message(self, req):
            pushed["req"] = req

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    fake_module = MagicMock()
    fake_module.AsyncMessagingApi = lambda c: FakeApi()
    fake_module.AsyncApiClient = lambda cfg: FakeClient()
    fake_module.Configuration = lambda access_token=None: MagicMock()
    fake_module.PushMessageRequest = lambda to=None, messages=None: {
        "to": to, "messages": messages,
    }
    fake_module.TextMessage = lambda text=None: {"type": "text", "text": text}
    fake_module.FlexMessage = lambda alt_text=None, contents=None: {
        "type": "flex", "altText": alt_text, "contents": contents,
    }
    fake_module.FlexContainer = MagicMock()
    fake_module.FlexContainer.from_dict = lambda d: d

    class _ApiExc(Exception):
        pass
    fake_module.ApiException = _ApiExc

    with patch.dict("sys.modules", {"linebot.v3.messaging": fake_module}):
        w = LinePushOutboxWorker()
        ok, err = await w._push_to_line(
            "Uxxx", [{"type": "text", "text": "hello"}],
        )
    assert ok is True
    assert err is None
    assert pushed["req"]["to"] == "Uxxx"
    assert pushed["req"]["messages"][0]["text"] == "hello"


@pytest.mark.asyncio
async def test_push_to_line_passes_retry_key(monkeypatch):
    """CR-0175 C：帶 retry_key 時傳 x_line_retry_key=outbox_id 給 push_message
    (讓 LINE 對同一 row 的 crash-replay 重送 24h 去重，閉合 R19)。"""
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    pushed = {}

    class FakeApi:
        async def push_message(self, req, x_line_retry_key=None):
            pushed["req"] = req
            pushed["retry_key"] = x_line_retry_key

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    fake_module = MagicMock()
    fake_module.AsyncMessagingApi = lambda c: FakeApi()
    fake_module.AsyncApiClient = lambda cfg: FakeClient()
    fake_module.Configuration = lambda access_token=None: MagicMock()
    fake_module.PushMessageRequest = lambda to=None, messages=None: {
        "to": to, "messages": messages,
    }
    fake_module.TextMessage = lambda text=None: {"type": "text", "text": text}
    fake_module.FlexMessage = lambda alt_text=None, contents=None: {}
    fake_module.FlexContainer = MagicMock()

    class _ApiExc(Exception):
        pass
    fake_module.ApiException = _ApiExc

    with patch.dict("sys.modules", {"linebot.v3.messaging": fake_module}):
        w = LinePushOutboxWorker()
        ok, err = await w._push_to_line(
            "Uxxx", [{"type": "text", "text": "hi"}],
            retry_key="outbox-uuid-123",
        )
    assert ok is True
    assert pushed["retry_key"] == "outbox-uuid-123"


@pytest.mark.asyncio
async def test_push_to_line_flex_message_path(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    pushed = {}

    class FakeApi:
        async def push_message(self, req):
            pushed["req"] = req

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    fake_module = MagicMock()
    fake_module.AsyncMessagingApi = lambda c: FakeApi()
    fake_module.AsyncApiClient = lambda cfg: FakeClient()
    fake_module.Configuration = lambda access_token=None: MagicMock()
    fake_module.PushMessageRequest = lambda to=None, messages=None: {
        "to": to, "messages": messages,
    }
    fake_module.TextMessage = lambda text=None: {"type": "text", "text": text}
    fake_module.FlexMessage = lambda alt_text=None, contents=None: {
        "type": "flex", "altText": alt_text, "contents": contents,
    }
    fake_module.FlexContainer = MagicMock()
    fake_module.FlexContainer.from_dict = lambda d: {"_parsed": d}

    class _ApiExc(Exception):
        pass
    fake_module.ApiException = _ApiExc

    with patch.dict("sys.modules", {"linebot.v3.messaging": fake_module}):
        w = LinePushOutboxWorker()
        ok, err = await w._push_to_line(
            "Uxxx",
            [{"type": "flex", "altText": "alt", "contents": {"type": "bubble"}}],
        )
    assert ok is True
    msg = pushed["req"]["messages"][0]
    assert msg["type"] == "flex"
    assert msg["altText"] == "alt"
    assert msg["contents"] == {"_parsed": {"type": "bubble"}}


@pytest.mark.asyncio
async def test_push_to_line_api_exception(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")

    class _ApiExc(Exception):
        def __init__(self, status):
            super().__init__("api fail")
            self.status = status

    class FakeApi:
        async def push_message(self, req):
            raise _ApiExc(status=429)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    fake_module = MagicMock()
    fake_module.AsyncMessagingApi = lambda c: FakeApi()
    fake_module.AsyncApiClient = lambda cfg: FakeClient()
    fake_module.Configuration = lambda access_token=None: MagicMock()
    fake_module.PushMessageRequest = lambda to=None, messages=None: {}
    fake_module.TextMessage = lambda text=None: {"type": "text", "text": text}
    fake_module.FlexMessage = lambda alt_text=None, contents=None: {}
    fake_module.FlexContainer = MagicMock()
    fake_module.ApiException = _ApiExc

    with patch.dict("sys.modules", {"linebot.v3.messaging": fake_module}):
        w = LinePushOutboxWorker()
        ok, err = await w._push_to_line("U1", [{"type": "text", "text": "x"}])
    assert ok is False
    assert "429" in err


@pytest.mark.asyncio
async def test_mark_failed_escalates_to_dead_at_max_attempts():
    """attempts +1 達到 max → 應走 _mark_dead 不再排 next_attempt_at。"""
    w = LinePushOutboxWorker()
    dead_called = {}
    failed_called = {}

    async def fake_dead(outbox_id, err):
        dead_called["id"] = outbox_id

    async def fake_db_exec(sql, args):
        failed_called["sql"] = sql

    w._mark_dead = fake_dead

    # patch db_module._conn.execute 用 monkeypatch 不便（_conn 可能 None）
    import realtime.line_push_outbox_worker as worker_mod

    class FakeConn:
        async def execute(self, sql, args):
            failed_called["sql"] = sql
            failed_called["args"] = args
            return MagicMock()

    original_conn = getattr(worker_mod.db_module, "_conn", None)
    worker_mod.db_module._conn = FakeConn()
    try:
        # current_attempts=4, max=5 → new=5 → 達 max → dead
        await w._mark_failed("ob-1", current_attempts=4, max_attempts=5, err="x")
        assert dead_called.get("id") == "ob-1"
        assert "sql" not in failed_called  # 未走 UPDATE backoff path

        # current_attempts=2, max=5 → new=3 → backoff
        await w._mark_failed("ob-2", current_attempts=2, max_attempts=5, err="y")
        assert "sql" in failed_called
        assert failed_called["args"][0] == 3  # new_attempts
    finally:
        worker_mod.db_module._conn = original_conn


def test_backoff_schedule_matches_design():
    """文件設計：30s, 2min, 8min, 30min, 2hr。"""
    assert _BACKOFF_SECONDS_BY_ATTEMPT == [30, 120, 480, 1800, 7200]
