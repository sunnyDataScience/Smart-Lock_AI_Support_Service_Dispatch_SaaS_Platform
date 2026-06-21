"""Deprecation v1 hit metrics — P4 Cutover 規劃用。

2 endpoints:
  1. GET  /admin/deprecation/v1-metrics      列出 v1 endpoint 命中次數（降序）
  2. POST /admin/deprecation/v1-metrics:reset 清空 counter（admin manual reset）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.deps import FULL_ACCESS_ROLES, CurrentUser, require_tenant, role_required
from middleware.deprecation import get_v1_hit_metrics, reset_v1_hit_metrics

router = APIRouter()


@router.get(
    "/admin/deprecation/v1-metrics",
    operation_id="listV1DeprecationMetrics",
    summary="列 /api/v1/* 命中次數降序（P4 Cutover 規劃用）",
    response_model=dict,
)
async def list_v1_metrics(
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    items = get_v1_hit_metrics()
    return {
        "items": items,
        "total_endpoints": len(items),
        "total_hits": sum(it["count"] for it in items),
    }


@router.post(
    "/admin/deprecation/v1-metrics:reset",
    operation_id="resetV1DeprecationMetrics",
    summary="清空 v1 hit counter（admin manual）",
    response_model=dict,
)
async def reset_v1_metrics(
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
) -> dict:
    reset_v1_hit_metrics()
    return {"status": "reset_ok"}
