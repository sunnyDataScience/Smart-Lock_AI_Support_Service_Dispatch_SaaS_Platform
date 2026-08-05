"""請求限流 middleware（CR-0209 TC-PERF-04 / NFR-Perf-004）。

WHY 這個檔案存在：`api/config.toml` 的 `[rate_limit]` 段自 2026 初就在，
`core/config.py:21,48` 也把它讀成 dict——但**沒有任何 middleware 消費它**。
`main.py:248` 只是把 `RateLimit-*` 三個 header 加進 CORS 的 expose_headers，
而那些 header 從來沒有被任何人設定過。也就是限流是一段完整的死設定：
看起來有、實際上零效果，而 429 的錯誤碼映射（`core/errors.py:54,66`）也一直沒有觸發點。

**預設維持關閉**（`enabled = false`）。要不要真的開、門檻設多少，是營運決策
不是工程決策——單品牌尚無真實流量，貿然開啟只會擋到自己的壓測與 UAT。
本模組把「能開」這件事準備好：翻 config 一個值即生效，不需再改 code。

演算法：per-key token bucket，in-process。
**已知限制（刻意）**：多實例部署時每個實例各自計數，實際上限是
`requests_per_minute × 實例數`。要精確跨實例限流需要 Redis 之類的共享狀態，
那是另一個決策（多一個必須常駐的相依）。對「擋住異常暴衝」這個目的，
per-instance 已經夠用；對「精確計費式配額」則不夠——本模組不宣稱後者。
"""
from __future__ import annotations

import time
from collections import OrderedDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 限流不套用的路徑（健康檢查被擋會讓 Cloud Run 誤判實例不健康 → 重啟迴圈）
_EXEMPT_PREFIXES = ("/health", "/metrics", "/docs", "/openapi.json", "/redoc")

# 追蹤的 key 數上限——防止被大量偽造 key 打爆記憶體（LRU 淘汰）
_MAX_TRACKED_KEYS = 10_000


class _Bucket:
    __slots__ = ("tokens", "updated_at")

    def __init__(self, tokens: float, updated_at: float) -> None:
        self.tokens = tokens
        self.updated_at = updated_at


class RateLimitMiddleware(BaseHTTPMiddleware):
    """per-key token bucket。`enabled=False` 時完全直通（零額外成本）。

    key 取用順序：認證身分 > 來源 IP。用身分優先是因為同一個 NAT 後面可能有多個
    正常使用者，用 IP 會誤傷；而未認證請求只有 IP 可用。
    """

    def __init__(self, app, *, enabled: bool = False, requests_per_minute: int = 120) -> None:
        super().__init__(app)
        self.enabled = bool(enabled)
        self.rpm = max(1, int(requests_per_minute))
        self._refill_per_sec = self.rpm / 60.0
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()

    def _key(self, request: Request) -> str:
        auth = request.headers.get("authorization") or ""
        if auth:
            # 只取 token 尾段做 key，不留完整憑證在記憶體
            return "auth:" + auth[-24:]
        client = request.client
        return "ip:" + (client.host if client else "unknown")

    def _take(self, key: str, now: float) -> tuple[bool, float, float]:
        """取一個 token。回 (是否放行, 剩餘 token, 距離補滿的秒數)。"""
        b = self._buckets.get(key)
        if b is None:
            if len(self._buckets) >= _MAX_TRACKED_KEYS:
                self._buckets.popitem(last=False)  # LRU 淘汰最舊的
            b = _Bucket(float(self.rpm), now)
            self._buckets[key] = b
        else:
            self._buckets.move_to_end(key)
            elapsed = max(0.0, now - b.updated_at)
            b.tokens = min(float(self.rpm), b.tokens + elapsed * self._refill_per_sec)
            b.updated_at = now

        reset_after = (self.rpm - b.tokens) / self._refill_per_sec if b.tokens < self.rpm else 0.0
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True, b.tokens, reset_after
        return False, b.tokens, max(1.0, (1.0 - b.tokens) / self._refill_per_sec)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.url.path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        allowed, remaining, reset_after = self._take(self._key(request), time.monotonic())
        headers = {
            "RateLimit-Limit": str(self.rpm),
            "RateLimit-Remaining": str(max(0, int(remaining))),
            "RateLimit-Reset": str(int(reset_after) + 1),
        }
        if not allowed:
            headers["Retry-After"] = str(int(reset_after) + 1)
            # 錯誤信封對齊 core/errors.py 的既有形狀（前端錯誤字典已有 RATE_LIMITED）
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED",
                                   "message": "請求過於頻繁，請稍後再試"}},
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response
