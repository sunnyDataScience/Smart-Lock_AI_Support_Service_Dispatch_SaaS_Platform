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


# ── 錯誤分類 → 重試判定 ─────────────────────────────────────────────────
#
# WHY：原本 except 分支無論什麼例外都寫死 error_kind="connection"，而
# "connection" 落在 base._TRANSIENT_ERROR_KINDS 裡，於是 _is_transient_response
# 對**每一種**錯誤都回 True：401/403 帳務封鎖、429 配額耗盡、400 參數錯誤
# 全部照重試。base 本來備好了 _NON_RETRYABLE_429_ERROR_TOKENS 要擋配額耗盡，
# 但沒有 status_code/code 就永遠走不到那條分支。
#
# 上面那支 test_chat_error_maps_to_error_response 只驗 finish_reason 與 content，
# 改前改後都會過——所以本區塊補的是「分類對不對」，才是真正的守線。


class _FakeLiteLLMError(Exception):
    """模擬 litellm 例外的形狀（沿用 openai SDK 的 status_code / code / type）。"""

    def __init__(self, message, *, status_code=None, code=None, type=None):  # noqa: A002
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.type = type


def _error_resp(monkeypatch, exc):
    async def boom(**kwargs):
        raise exc
    monkeypatch.setattr(litellm, "acompletion", boom)
    return asyncio.run(LiteLLMProvider().chat([{"role": "user", "content": "x"}]))


def test_quota_exhausted_429_is_not_retried(monkeypatch):
    """配額耗盡的 429 不可重試——重試只會把剩餘配額也燒光,客人還是等不到回覆。"""
    resp = _error_resp(monkeypatch, _FakeLiteLLMError(
        "You exceeded your current quota",
        status_code=429, code="insufficient_quota", type="insufficient_quota"))

    assert resp.error_status_code == 429
    assert resp.error_code == "insufficient_quota"
    assert LiteLLMProvider._is_transient_response(resp) is False


def test_rate_limit_429_is_still_retried(monkeypatch):
    """反向：一般速率限制的 429 仍要重試,不可因為修配額而把它一起擋掉。"""
    resp = _error_resp(monkeypatch, _FakeLiteLLMError(
        "Rate limit reached", status_code=429, code="rate_limit_exceeded"))

    assert LiteLLMProvider._is_transient_response(resp) is True


def test_auth_and_billing_block_403_is_not_retried(monkeypatch):
    """403（帳務封鎖／權限不足）重試絕無可能成功,只是讓客人多等一個重試預算。

    2026-08 的實況:Vertex AI 被 GCP 帳單分級封鎖回 403,修復前每一輪 turn
    都會把重試跑滿才吐罐頭回覆。
    """
    resp = _error_resp(monkeypatch, _FakeLiteLLMError(
        "Permission denied on resource", status_code=403, code="permission_denied"))

    assert resp.error_status_code == 403
    assert LiteLLMProvider._is_transient_response(resp) is False


def test_bad_request_400_is_not_retried(monkeypatch):
    """400 是我方送錯參數,重試送一樣的東西還是一樣錯。"""
    resp = _error_resp(monkeypatch, _FakeLiteLLMError(
        "Invalid request", status_code=400, code="invalid_request_error"))

    assert LiteLLMProvider._is_transient_response(resp) is False


def test_server_error_500_is_retried(monkeypatch):
    """5xx 是對方暫時性故障,要重試。"""
    resp = _error_resp(monkeypatch, _FakeLiteLLMError("upstream boom", status_code=503))

    assert LiteLLMProvider._is_transient_response(resp) is True


def test_connection_error_without_status_is_retried(monkeypatch):
    """連線類例外常常沒有 status_code,靠類名判定,必須仍然重試。"""

    class APIConnectionError(_FakeLiteLLMError):
        pass

    resp = _error_resp(monkeypatch, APIConnectionError("failed to establish connection"))

    assert resp.error_kind == "connection"
    assert LiteLLMProvider._is_transient_response(resp) is True


def test_timeout_without_status_is_retried(monkeypatch):
    """逾時同理。"""

    class Timeout(_FakeLiteLLMError):
        pass

    resp = _error_resp(monkeypatch, Timeout("request timed out"))

    assert LiteLLMProvider._is_transient_response(resp) is True
