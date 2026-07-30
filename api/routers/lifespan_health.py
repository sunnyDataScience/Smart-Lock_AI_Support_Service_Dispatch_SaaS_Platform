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

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required

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
        # CR-0189 §8（業主 2026-07-30 裁決：dead 事件接後台頁 + 告警）：
        # 這支 worker 原本不在本清單內——它負責重送 commission.accrued，
        # 掛掉的話佣金投影會靜默停止同步而沒有任何面板看得出來。
        ("commission_outbox", "realtime.commission_outbox_worker", "worker"),
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
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    monitors = _collect_monitors()
    total = len(monitors)
    by_state: dict[str, int] = {}
    for v in monitors.values():
        state = v.get("state", "unknown")
        by_state[state] = by_state.get(state, 0) + 1
    all_running = by_state.get("running", 0) == total

    # CR-0189 §8：outbox 積壓與 dead 計數。
    # 「worker 在跑」不等於「事件送得出去」——worker 可以健康地一直重試失敗。
    # dead 代表重試耗盡：**settlement 已存在、款照付**，遺失的是跨庫佣金投影同步，
    # 所以不是付款事故但技師端看不到該筆佣金 → 需人工重放（保留 event_id 故冪等）。
    outbox: dict[str, Any] = {}
    try:
        from realtime.commission_outbox_worker import worker as _cw
        # 方法名是 get_job_sli（不是 metrics）——寫錯會被下面的 except 吞成靜默失效，
        # 故本檔的守線測試會斷言此欄真的有值。
        outbox = dict(await _cw.get_job_sli())
        dead = int(outbox.get("retry_exhausted_total", 0) or 0)
        oldest = float(outbox.get("oldest_pending_seconds", 0) or 0)
        outbox["needs_manual_replay"] = dead > 0
        # 積壓門檻取 15 分鐘：worker 預設輪詢遠短於此，超過即代表重試在打轉
        outbox["backlog_stalled"] = oldest > 900
        outbox["replay_hint"] = (
            "SELECT id, event_id, reconciliation_id, last_error FROM "
            "commission_event_outbox WHERE status = 'dead';"
        ) if dead > 0 else None
        if dead > 0:
            logger.error(
                "commission outbox 有 %d 筆 dead 事件待人工重放（佣金投影未同步）", dead)
    except Exception as e:  # noqa: BLE001 — 指標取不到不可讓健康頁整頁掛掉
        outbox = {"error": f"{type(e).__name__}: {e}"}

    # 告警旗標：讓監控只需盯一個布林，不必自己組合條件
    alert = (
        not all_running
        or bool(outbox.get("needs_manual_replay"))
        or bool(outbox.get("backlog_stalled"))
        or "error" in outbox
    )
    return {
        "monitors": monitors,
        "commission_outbox": outbox,
        "summary": {
            "total": total,
            "by_state": by_state,
            "all_running": all_running,
            "alert": alert,
        },
    }
