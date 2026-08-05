"""agent → api 的 trace 傳播（CR-0209 TC-NFR-OBS-01）。

WHY：agent 有 `line.webhook` / `agent.turn` 兩個 span，api 有 FastAPI 自動埋點，
但**兩邊的 trace 是斷開的**——agent 打給 api 的 httpx 請求沒帶 traceparent，
SigNoz 上看到的是兩棵互不相關的樹。一則客人訊息從 webhook 進來、轉發到 api 建卡、
再由 worker 推播出去，這條鏈在 trace 上完全串不起來，出事時只能靠時間戳猜。

注入點放在 `_bridge_auth_headers` 是因為五個呼叫端有四個共用它，一改全中；
第五處（LINE 簽章轉發）單獨注入。
"""
from __future__ import annotations

from lockcore.channels.line_gateway import _bridge_auth_headers
from lockcore.observability import inject_trace_headers


def test_no_traceparent_when_observability_disabled():
    """未啟用時零行為變化——不可因為加了 trace 就改變既有 header。"""
    h = _bridge_auth_headers("tok")
    assert "traceparent" not in h
    assert h in ({"X-Internal-Token": "tok"}, {"X-Service-Credential": "tok"})


def test_auth_headers_preserved():
    """注入不得吃掉原有的認證 header（那會讓服務間呼叫全部 401）。"""
    assert _bridge_auth_headers("abc")["X-Internal-Token"] == "abc"


def test_inject_is_pure_and_never_raises():
    """回新 dict 不改原物件；任何情況都不 raise（trace 失敗不可影響主流程）。"""
    src = {"Content-Type": "application/json"}
    out = inject_trace_headers(src)
    assert out is not src, "應回新 dict，不可就地改呼叫端的物件"
    assert out["Content-Type"] == "application/json"
    assert inject_trace_headers(None) == {}


def test_inject_calls_propagator_when_enabled(monkeypatch):
    """啟用時要真的呼叫 W3C propagator 並把結果併進 headers。

    用假 propagator 而非真 OTel：`opentelemetry` 是 optional extra，本機與 CI
    都沒裝，用真套件寫的測試只會 skip —— **skip 的測試等於沒有測試**。
    這裡驗的是我們自己的邏輯（啟用判定、dict 複製、結果合併），
    propagator 本身是上游套件的責任。
    """
    import sys
    import types

    import lockcore.observability as obs

    called = {}

    def _fake_inject(carrier):
        called["carrier"] = carrier
        carrier["traceparent"] = "00-abc-def-01"

    fake_mod = types.ModuleType("opentelemetry.propagate")
    fake_mod.inject = _fake_inject
    monkeypatch.setitem(sys.modules, "opentelemetry", types.ModuleType("opentelemetry"))
    monkeypatch.setitem(sys.modules, "opentelemetry.propagate", fake_mod)
    monkeypatch.setattr(obs, "_enabled", True)

    out = obs.inject_trace_headers({"a": "b"})

    assert out["a"] == "b", "原有 header 不可被吃掉"
    assert out["traceparent"] == "00-abc-def-01"
    assert called["carrier"] is out, "應把要送出的 headers 本身交給 propagator"


def test_inject_swallows_propagator_failure(monkeypatch):
    """propagator 爆炸時必須吞掉——trace 傳播失敗絕不可影響服務間呼叫。"""
    import sys
    import types

    import lockcore.observability as obs

    def _boom(_carrier):
        raise RuntimeError("propagator exploded")

    fake_mod = types.ModuleType("opentelemetry.propagate")
    fake_mod.inject = _boom
    monkeypatch.setitem(sys.modules, "opentelemetry", types.ModuleType("opentelemetry"))
    monkeypatch.setitem(sys.modules, "opentelemetry.propagate", fake_mod)
    monkeypatch.setattr(obs, "_enabled", True)

    out = obs.inject_trace_headers({"X-Internal-Token": "tok"})
    assert out == {"X-Internal-Token": "tok"}, "失敗時應原樣回傳，認證 header 不可遺失"
