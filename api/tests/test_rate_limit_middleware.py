"""限流 middleware（CR-0209 TC-PERF-04 / NFR-Perf-004）。

WHY：`api/config.toml` 的 `[rate_limit]` 段與 `core/config.py:21,48` 的讀取
自始就在，但**沒有任何 middleware 消費它**——限流是一段完整的死設定，
`RateLimit-*` 三個 header 也從來沒被任何人設定過（main.py 只是把它們加進
CORS 的 expose_headers）。429 的錯誤碼映射（core/errors.py:54,66）同樣沒有觸發點。

**預設維持關閉。** 本測試同時釘住「關閉時零行為變化」——那是它能安全合進主線的前提。
"""
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.rate_limit import RateLimitMiddleware


def _app(*, enabled: bool, rpm: int = 3) -> TestClient:
    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[
        Route("/x", ok),
        Route("/health", ok),
    ])
    app.add_middleware(RateLimitMiddleware, enabled=enabled, requests_per_minute=rpm)
    return TestClient(app)


def test_disabled_is_completely_transparent():
    """關閉時不擋、也不加 header —— 零行為變化是合進主線的前提。"""
    c = _app(enabled=False)
    for _ in range(50):
        r = c.get("/x")
        assert r.status_code == 200
    assert "RateLimit-Limit" not in r.headers


def test_enabled_allows_up_to_limit_then_429():
    c = _app(enabled=True, rpm=3)
    codes = [c.get("/x").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200], f"額度內被擋：{codes}"
    assert codes[3:] == [429, 429], f"超額未被擋：{codes}"


def test_429_body_and_headers():
    c = _app(enabled=True, rpm=1)
    c.get("/x")
    r = c.get("/x")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert r.headers["RateLimit-Limit"] == "1"
    assert int(r.headers["Retry-After"]) >= 1


def test_health_is_exempt():
    """健康檢查被擋會讓 Cloud Run 誤判實例不健康 → 重啟迴圈。"""
    c = _app(enabled=True, rpm=1)
    for _ in range(10):
        assert c.get("/health").status_code == 200


def test_headers_present_on_success_when_enabled():
    c = _app(enabled=True, rpm=5)
    r = c.get("/x")
    assert r.status_code == 200
    assert r.headers["RateLimit-Limit"] == "5"
    assert int(r.headers["RateLimit-Remaining"]) <= 5


def test_tracked_keys_are_bounded():
    """偽造大量 key 不得把記憶體打爆（LRU 淘汰）。"""
    from core.rate_limit import _MAX_TRACKED_KEYS, RateLimitMiddleware as M

    mw = M(None, enabled=True, requests_per_minute=10)
    import time
    now = time.monotonic()
    for i in range(_MAX_TRACKED_KEYS + 200):
        mw._take(f"ip:{i}", now)
    assert len(mw._buckets) <= _MAX_TRACKED_KEYS


def test_tokens_refill_over_time():
    """時間經過後 token 要補回來，不是一次用完就永久 429。"""
    import time
    from core.rate_limit import RateLimitMiddleware as M

    mw = M(None, enabled=True, requests_per_minute=60)   # 每秒補 1
    t = time.monotonic()
    for _ in range(60):
        mw._take("ip:a", t)
    allowed, _, _ = mw._take("ip:a", t)
    assert allowed is False
    allowed2, _, _ = mw._take("ip:a", t + 5)   # 5 秒後應補回約 5 個
    assert allowed2 is True
