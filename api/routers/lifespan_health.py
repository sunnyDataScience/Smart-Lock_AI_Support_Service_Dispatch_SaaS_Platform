"""Lifespan Monitor Health — admin 查 8 個背景 monitor 健康狀態。

對應本 session 累積至 8-monitor 啟動序：
  inventory → sla → line_push → recon_exc → dispute_escalation →
  canary_advance → statement_auto_approval → gdpr_hard_delete

每個 monitor 都有 `_task: asyncio.Task | None` + `_stopping: asyncio.Event`
本 endpoint 動態檢查 task done 狀態 + stopping 旗標推導 running/stopped。

1 endpoint:
  GET /admin/lifespan-monitors/health
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from core.deps import CurrentUser, require_tenant

logger = logging.getLogger("api.lifespan_health")

router = APIRouter()


def _monitor_status(monitor: Any) -> dict[str, Any]:
    """從 monitor instance 推導 health。

    每個 monitor 都實作 `_task` + `_stopping` 兩屬性 (BG worker pattern)。
    """
    task = getattr(monitor, "_task", None)
    stopping = getattr(monitor, "_stopping", None)
    interval = getattr(monitor, "_interval", None)

    is_started = task is not None
    is_done = task.done() if task else None
    is_stopping = bool(stopping and stopping.is_set()) if stopping else None

    if not is_started:
        state = "not_started"
    elif is_stopping:
        state = "stopping"
    elif is_done:
        state = "crashed"  # task done 但 stopping 未 set → 異常終止
    else:
        state = "running"

    return {
        "state": state,
        "interval_seconds": interval,
        "task_started": is_started,
        "task_done": is_done,
        "stopping_signal": is_stopping,
    }


def _collect_monitors() -> dict[str, Any]:
    """動態 import 8 個 monitor 並收集 health。

    失敗（未 mount）的 monitor 標 `import_error`。
    """
    monitors_meta = [
        ("inventory", "realtime.inventory_monitor", "monitor"),
        ("sla", "realtime.sla_monitor", "monitor"),
        ("line_push_outbox", "realtime.line_push_outbox_worker", "worker"),
        ("reconciliation_exception", "realtime.reconciliation_exception_detector", "worker"),
        ("dispute_escalation", "realtime.dispute_escalation_cron", "worker"),
        ("config_canary_advance", "realtime.config_canary_advance_cron", "worker"),
        ("statement_auto_approval", "realtime.statement_auto_approval_cron", "worker"),
        ("gdpr_hard_delete", "realtime.gdpr_hard_delete_cron", "worker"),
        ("webhook_idem_cleanup", "realtime.webhook_idempotency_cleanup_cron", "worker"),
        ("family_review_sla", "realtime.family_review_sla_cron", "worker"),
    ]

    result: dict[str, Any] = {}
    for name, module_path, attr in monitors_meta:
        try:
            module = __import__(module_path, fromlist=[attr])
            mon = getattr(module, attr)
            result[name] = _monitor_status(mon)
        except Exception as e:  # noqa: BLE001
            result[name] = {
                "state": "import_error",
                "error": f"{type(e).__name__}: {e}",
            }
    return result


@router.get(
    "/admin/lifespan-monitors/health",
    operation_id="getLifespanMonitorsHealth",
    summary="查 8 個背景 monitor 健康狀態（running / stopping / crashed / not_started）",
    response_model=dict,
)
async def get_health(
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    monitors = _collect_monitors()
    total = len(monitors)
    by_state: dict[str, int] = {}
    for v in monitors.values():
        state = v.get("state", "unknown")
        by_state[state] = by_state.get(state, 0) + 1
    all_running = by_state.get("running", 0) == total
    return {
        "monitors": monitors,
        "summary": {
            "total": total,
            "by_state": by_state,
            "all_running": all_running,
        },
    }
