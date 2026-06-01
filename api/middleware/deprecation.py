"""legacy `/api/v1/*` 回應一律加 `Deprecation: true` header（CR-0002-α D3 雙掛過渡）。

tenant-scoped v2 上線後，所有 `/api/v1` 表面視為 deprecated（**不設 Sunset 日期** — C-11/D3
業主裁決：保留全部 legacy、只標 Deprecation）。

為何放 middleware 而非各 route handler：
  1. 覆蓋**全部** legacy 端點（含尚未個別遷移的 ~40 條 C-11），不需逐 route 加 code。
  2. **error 回應也帶**：route handler 內 `response.headers["Deprecation"]` 在 raise（404/403…）
     時會隨被丟棄的 Response 一起遺失；middleware 包在 exception handler 外層，看得到轉換後的
     最終回應，故 4xx/5xx 也會被蓋上 header。
  3. 單一事實來源，避免各 route 重複且易漏。

successor-version 的 `Link` header 仍由各「已有 v2 對應」的 route 自行附加（middleware 無法
知道每條 legacy 對應哪個 v2 path）。
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/v1"):
            response.headers["Deprecation"] = "true"
        return response
