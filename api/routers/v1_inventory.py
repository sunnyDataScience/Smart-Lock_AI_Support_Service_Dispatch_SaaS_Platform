"""V1 Routers Inventory — P4 Cutover 規劃工具 (補強 deprecation_metrics)。

提供動態列出當前 mounted /api/v1/* endpoint 的端點 — 供 P4 BUILD admin
盤點哪些 v1 router 還在；與 deprecation_metrics 配合：

  - deprecation_metrics：runtime hit count (有流量的)
  - v1_inventory：static mounted list (有 endpoint 註冊的)

→ inventory - metrics = 沒流量的 v1 endpoint，可優先刪。

2 endpoints:
  1. GET /admin/v1-inventory                列所有 mounted v1 endpoint
  2. GET /admin/v1-inventory/no-traffic     列 mounted 但 0 hit metrics 的 (P4 刪除候選)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request

from core.deps import CurrentUser, require_tenant
from middleware.deprecation import get_v1_hit_metrics

logger = logging.getLogger("api.v1_inventory")

router = APIRouter()


def _collect_v1_routes(app) -> list[dict[str, Any]]:
    """掃 app.routes 找所有 /api/v1/* path → list。"""
    items = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or not path.startswith("/api/v1"):
            continue
        methods = list(getattr(route, "methods", []) or [])
        # 排除 HEAD/OPTIONS（FastAPI 自動加）
        methods = [m for m in methods if m not in ("HEAD", "OPTIONS")]
        if not methods:
            continue
        items.append({
            "path": path,
            "methods": sorted(methods),
            "operation_id": getattr(route, "operation_id", None),
            "name": getattr(route, "name", None),
        })
    items.sort(key=lambda x: x["path"])
    return items


@router.get(
    "/admin/v1-inventory",
    operation_id="listV1RouterInventory",
    summary="列所有 mounted /api/v1/* endpoint（P4 Cutover 規劃用）",
    response_model=dict,
)
async def list_v1_inventory(
    request: Request,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    items = _collect_v1_routes(request.app)
    return {
        "items": items,
        "total": len(items),
    }


@router.get(
    "/admin/v1-inventory/no-traffic",
    operation_id="listV1RoutersWithoutTraffic",
    summary="列 mounted 但 0 hit count 的 v1 endpoint（P4 刪除候選）",
    response_model=dict,
)
async def list_no_traffic(
    request: Request,
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """列 mounted 但 metrics 顯示 0 hit 的 v1 endpoint。

    用於 P4 BUILD 決策：上線 30 天後跑此 endpoint，回傳的 list 即為
    安全刪除候選（路徑被 mount 但無實際流量）。

    注：metrics 為 in-memory 重啟歸零；建議搭 reset → 30 天觀察 → 查看。
    """
    inventory = _collect_v1_routes(request.app)
    metrics = get_v1_hit_metrics()
    # metrics key 是 normalized (method, path)
    has_hit: set[tuple[str, str]] = set()
    for m in metrics:
        if m["count"] > 0:
            has_hit.add((m["method"], m["path"]))

    candidates = []
    for item in inventory:
        # 對每 method 各別比對 — 同 path 不同 method 獨立判定
        all_no_traffic_methods = []
        for method in item["methods"]:
            if (method, item["path"]) not in has_hit:
                all_no_traffic_methods.append(method)
        if all_no_traffic_methods:
            candidates.append({
                "path": item["path"],
                "methods_without_traffic": all_no_traffic_methods,
                "operation_id": item["operation_id"],
            })
    return {
        "candidates": candidates,
        "total_candidates": len(candidates),
        "total_mounted": len(inventory),
        "note": (
            "metrics 為 in-memory 重啟歸零；P4 BUILD 前建議"
            "reset 後觀察 30 天再查此 endpoint。"
        ),
    }
