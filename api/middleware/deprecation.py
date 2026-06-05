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

**Hit metrics (P4 Cutover 規劃用，2026-06-05)**：in-memory counter 記每個 v1 path 的命中次數，
給 admin via `GET /admin/deprecation/v1-metrics` 取出 → 線上跑一段時間後即可看哪些 v1 endpoint
仍有流量，安全刪除哪些。重啟歸零；多 worker deploy 統計不準（單機 in-memory）。
"""

from __future__ import annotations

import re
from collections import defaultdict
from threading import Lock
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# In-memory hit counter（P4 BUILD 規劃用）
# key: (method, normalized_path) e.g. ('GET', '/api/v1/refunds')
# value: count
_v1_hits: dict[tuple[str, str], int] = defaultdict(int)
_v1_hits_lock = Lock()

# 把 /api/v1/refunds/abc-123 normalize 成 /api/v1/refunds/{id}
# 簡化版：UUID + 純數字 ID 都歸 {id}
_UUID_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)
_NUMERIC_RE = re.compile(r"/\d+(?=/|$)")


def _normalize_path(path: str) -> str:
    """把 /api/v1/refunds/<uuid> 與 /api/v1/refunds/<id> 都歸併 — metrics 聚合用。"""
    p = _UUID_RE.sub("/{id}", path)
    p = _NUMERIC_RE.sub("/{id}", p)
    return p


def get_v1_hit_metrics() -> list[dict[str, Any]]:
    """回 list of {method, path, count}，count 降序。

    供 admin endpoint 顯示用；P4 BUILD 規劃時參考。
    """
    with _v1_hits_lock:
        snapshot = list(_v1_hits.items())
    items = [
        {"method": k[0], "path": k[1], "count": v}
        for k, v in snapshot
    ]
    items.sort(key=lambda x: x["count"], reverse=True)
    return items


def reset_v1_hit_metrics() -> None:
    """清空 counter（admin manual reset 或測試用）。"""
    with _v1_hits_lock:
        _v1_hits.clear()


class DeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/v1"):
            response.headers["Deprecation"] = "true"
            # P4 Cutover 規劃用：記錄 hit counter
            key = (request.method.upper(), _normalize_path(path))
            with _v1_hits_lock:
                _v1_hits[key] += 1
        return response
