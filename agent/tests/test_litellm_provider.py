"""LiteLLMProvider 測試 — 不打真 API,monkeypatch litellm.acompletion 驗證映射。"""

import asyncio
import types

import litellm

from lockcore.providers.litellm_provider import LiteLLMProvider


def _fake_resp(content, tool_calls=None, finish="stop"):
    msg = types.SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=None)
    choice = types.SimpleNamespace(message=msg, finish_reason=finish)
    usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return types.SimpleNamespace(choices=[choice], usage=usage)


def test_get_default_model():
    assert LiteLLMProvider(default_model="claude-sonnet-4-5").get_default_model() == "claude-sonnet-4-5"


def test_chat_maps_content_and_usage(monkeypatch):
    async def fake(**kwargs):
        # 確認有把 model/messages 傳進 litellm
        assert kwargs["model"] == "claude-sonnet-4-5"
        assert kwargs["messages"]
        return _fake_resp("您好,這是鎖市客服")
    monkeypatch.setattr(litellm, "acompletion", fake)
    p = LiteLLMProvider(default_model="claude-sonnet-4-5", api_key="sk-test")
    resp = asyncio.run(p.chat([{"role": "user", "content": "你好"}]))
    assert resp.content == "您好,這是鎖市客服"
    assert resp.finish_reason == "stop"
    assert resp.usage["total_tokens"] == 15


def test_chat_maps_tool_calls(monkeypatch):
    tc = types.SimpleNamespace(
        id="t1", function=types.SimpleNamespace(name="transfer_to_human", arguments='{"reason":"報價"}')
    )
    async def fake(**kwargs):
        return _fake_resp(None, tool_calls=[tc], finish="tool_calls")
    monkeypatch.setattr(litellm, "acompletion", fake)
    resp = asyncio.run(LiteLLMProvider().chat([{"role": "user", "content": "多少錢"}], tools=[{"x": 1}]))
    assert resp.has_tool_calls
    assert resp.tool_calls[0].name == "transfer_to_human"
    assert resp.tool_calls[0].arguments == {"reason": "報價"}
    assert resp.finish_reason == "tool_calls"


def test_chat_error_maps_to_error_response(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(litellm, "acompletion", boom)
    resp = asyncio.run(LiteLLMProvider().chat([{"role": "user", "content": "x"}]))
    assert resp.finish_reason == "error"
    assert "network down" in resp.content
