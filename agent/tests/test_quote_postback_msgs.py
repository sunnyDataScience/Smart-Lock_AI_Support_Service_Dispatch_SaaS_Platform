"""CR-0178 UAT-0720-12 尾巴 — 報價回覆失敗話術依 error_code 分流。

背景：0720 外測「重複同意報價回『未送達（報價或已失效）』」誤導——冪等已由
FR-API-02 修（同決定重複→200）；本輪補「非冪等命中」情境的話術分流：
先同意後拒絕/先拒絕後同意（QUOTE_ALREADY_DECIDED）、真過期（QUOTE_EXPIRED）、
找不到（NOT_FOUND）各給準確話術；未知 code / body 非 JSON → 維持原 fallback 句。

stub pattern 仿 test_ops_postback_bridge.py（monkeypatch httpx.AsyncClient；
注意 quote 路徑 post 用 json=/headers= kwargs，非 ops 的 content=）。
"""
from __future__ import annotations

import pytest

from lockcore.channels.line_gateway import (
    _QUOTE_FAIL_FALLBACK,
    _quote_fail_reply,
    _route_quote_postback_safe,
)


# ── 純函式：話術選擇 ──────────────────────────────────

def test_reply_expired():
    out = _quote_fail_reply(409, {"error_code": "QUOTE_EXPIRED"}, "accept")
    assert "有效期限" in out


def test_reply_already_decided_by_direction():
    # 先同意後拒絕：這次按拒絕 → 告知已同意並安排
    out_r = _quote_fail_reply(409, {"error_code": "QUOTE_ALREADY_DECIDED"}, "reject")
    assert "已同意" in out_r
    # 先拒絕後同意：這次按同意 → 告知已拒絕
    out_a = _quote_fail_reply(409, {"error_code": "QUOTE_ALREADY_DECIDED"}, "accept")
    assert "已回覆拒絕" in out_a


def test_reply_not_found_and_forbidden():
    assert "找不到" in _quote_fail_reply(404, {"error_code": "NOT_FOUND"}, "accept")
    out = _quote_fail_reply(403, {"error_code": "FORBIDDEN"}, "accept")
    assert "無法由此帳號" in out
    # 話術不洩歸屬細節
    assert "擁有" not in out and "own" not in out


def test_reply_unknown_code_falls_back():
    assert _quote_fail_reply(409, {"error_code": "WEIRD"}, "accept") == _QUOTE_FAIL_FALLBACK
    assert _quote_fail_reply(500, {}, "reject") == _QUOTE_FAIL_FALLBACK


# ── 整合：stub httpx 走完整 postback 路徑 ─────────────────

def _stub_client(status: int, body=None, text: str | None = None):
    import httpx

    class _StubClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            req = httpx.Request("POST", url)
            if text is not None:
                return httpx.Response(status, text=text, request=req)
            return httpx.Response(status, json=body or {}, request=req)

    return _StubClient


@pytest.mark.asyncio
async def test_postback_expired_message(monkeypatch):
    import httpx

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t0ken")
    monkeypatch.setattr(
        httpx, "AsyncClient", _stub_client(409, {"error_code": "QUOTE_EXPIRED"})
    )
    out = await _route_quote_postback_safe("locksmart", "U1", "q:a|quote-1")
    assert out is not None and "有效期限" in out


@pytest.mark.asyncio
async def test_postback_already_decided_reject(monkeypatch):
    import httpx

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t0ken")
    monkeypatch.setattr(
        httpx, "AsyncClient",
        _stub_client(409, {"error_code": "QUOTE_ALREADY_DECIDED",
                           "details": [{"current_state": "accepted"}]}),
    )
    out = await _route_quote_postback_safe("locksmart", "U1", "q:r|quote-1")
    assert out is not None and "已同意" in out


@pytest.mark.asyncio
async def test_postback_non_json_body_falls_back(monkeypatch):
    import httpx

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t0ken")
    monkeypatch.setattr(
        httpx, "AsyncClient", _stub_client(502, text="<html>Bad Gateway</html>")
    )
    out = await _route_quote_postback_safe("locksmart", "U1", "q:a|quote-1")
    assert out == _QUOTE_FAIL_FALLBACK


@pytest.mark.asyncio
async def test_postback_success_unchanged(monkeypatch):
    import httpx

    monkeypatch.setenv("LOCK_API_BASE_URL", "http://api:8001")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t0ken")
    monkeypatch.setattr(
        httpx, "AsyncClient",
        _stub_client(200, {"data": {"state": "accepted"}, "error": None}),
    )
    out = await _route_quote_postback_safe("locksmart", "U1", "q:a|quote-1")
    assert out is not None and "已收到您的同意" in out
