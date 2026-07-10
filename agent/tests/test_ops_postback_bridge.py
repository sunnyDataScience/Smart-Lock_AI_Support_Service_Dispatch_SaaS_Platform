"""CR-0155:改約/範圍變更 postback 轉發橋(ADR-011 附註缺口)。

r:c|/r:r|/s:a|/s:r| → 原始 body+簽章原封轉發 api /api/v1/line/webhook;
非 ops postback 回 None;LOCK_API_BASE_URL 未設/HTTP 失敗 → 友善話術(fail-soft)。
"""

from __future__ import annotations

import asyncio

import pytest

from lockcore.channels.line_gateway import _forward_ops_postback_safe


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_non_ops_postback_returns_none(monkeypatch):
    monkeypatch.delenv("LOCK_API_BASE_URL", raising=False)
    assert await _forward_ops_postback_safe("{}", "sig", "q:a|abc") is None
    assert await _forward_ops_postback_safe("{}", "sig", "junk") is None
    assert await _forward_ops_postback_safe("{}", "sig", "") is None


@pytest.mark.asyncio
async def test_ops_postback_without_bridge_env_fail_soft(monkeypatch):
    monkeypatch.delenv("LOCK_API_BASE_URL", raising=False)
    out = await _forward_ops_postback_safe("{}", "sig", "s:a|scope-1")
    assert out is not None and "客服" in out  # 友善話術非 raise


@pytest.mark.asyncio
async def test_ops_postback_forwards_verbatim(monkeypatch):
    """轉發必須原封 body+簽章(api 端要重驗簽)。以 stub transport 攔截驗證。"""
    import httpx

    captured = {}

    class _StubClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            captured["url"] = url
            captured["content"] = content
            captured["signature"] = (headers or {}).get("X-Line-Signature")
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)

    raw = '{"events":[{"type":"postback","postback":{"data":"r:c|prop-1|2"}}]}'
    out = await _forward_ops_postback_safe(raw, "sig-abc", "r:c|prop-1|2")
    assert out is None  # 成功=靜默(api 端推確認)
    assert captured["url"] == "http://api:8001/api/v1/line/webhook"
    assert captured["content"] == raw.encode("utf-8")
    assert captured["signature"] == "sig-abc"


@pytest.mark.asyncio
async def test_ops_postback_http_error_fail_soft(monkeypatch):
    import httpx

    class _StubClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            return httpx.Response(500, text="boom", request=httpx.Request("POST", url))

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    out = await _forward_ops_postback_safe("{}", "sig", "s:r|scope-2")
    assert out is not None and "未送達" in out
