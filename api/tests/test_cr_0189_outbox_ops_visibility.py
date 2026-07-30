"""CR-0189 §8（業主 2026-07-30 裁決）：dead 事件接後台頁 + 告警。

WHY：
  `_mark_dead` 原本只 `logger.error`。dead 的語意是「重試耗盡」——**settlement 已存在、
  款照付**，遺失的是跨庫佣金投影同步，所以不是付款事故，但技師端永遠看不到那筆佣金，
  而沒有任何面板看得出來。

  另補一個原本就漏的：`commission_outbox` worker **不在** `/admin/lifespan-monitors/health`
  的 monitor 清單內——它掛掉的話佣金投影會靜默停止同步。

  也要注意「worker 在跑」≠「事件送得出去」：worker 可以很健康地一直重試失敗，
  所以健康頁除了 task 狀態，還要看 dead 計數與最舊 pending 的年齡。

本檔守三條線（這些都不是功能行為，只有靜態/契約測試抓得到）：
  1. commission_outbox worker 在 monitor 清單內。
  2. 健康端點回傳 `commission_outbox` 且**不是 error**——我第一版把方法名寫成
     `metrics()`（實際是 `get_job_sli()`），被 try/except 吞成靜默失效，本測試就是
     為了讓那種錯誤變成紅燈。
  3. 有單一 `summary.alert` 布林，監控不必自己組合條件。
"""

from __future__ import annotations

import inspect

import pytest

from routers import lifespan_health


@pytest.mark.unit
def test_commission_outbox_worker_is_monitored():
    src = inspect.getsource(lifespan_health._collect_monitors)
    assert "realtime.commission_outbox_worker" in src, (
        "commission_outbox worker 不在 monitor 清單 → 掛掉時佣金投影靜默停止同步"
    )


@pytest.mark.unit
def test_health_uses_the_real_sli_method_name():
    """釘住方法名。worker 提供的是 get_job_sli()，不是 metrics()。"""
    from realtime.commission_outbox_worker import worker

    assert hasattr(worker, "get_job_sli"), "worker 的 SLI 方法名改了，健康頁要同步改"
    src = inspect.getsource(lifespan_health.get_health)
    assert "get_job_sli" in src
    assert ".metrics()" not in src, "呼叫了不存在的 metrics() → 會被 except 吞成靜默失效"


async def test_health_reports_outbox_metrics_not_error():
    """實跑一次：commission_outbox 必須有真指標，不可是 {'error': ...}。"""
    from core.db import _ensure_conn
    if not await _ensure_conn():
        pytest.skip("DB unavailable")

    class _U:  # 端點只用 role_required 依賴，函式體不碰 user
        user_id = "00000000-0000-0000-0000-000000000000"
        role = "admin"
        tenant_id = "00000000-0000-0000-0000-000000000001"

    result = await lifespan_health.get_health(user=_U())
    ob = result.get("commission_outbox")
    assert isinstance(ob, dict), "健康頁必須回 commission_outbox"
    assert "error" not in ob, f"取指標失敗（靜默失效）：{ob.get('error')}"
    assert "retry_exhausted_total" in ob and "oldest_pending_seconds" in ob
    assert "needs_manual_replay" in ob and "backlog_stalled" in ob
    assert isinstance(result["summary"].get("alert"), bool), (
        "summary 要有單一 alert 布林供監控使用"
    )
    # commission_outbox worker 也必須出現在 monitors 內
    assert "commission_outbox" in result["monitors"]


async def test_alert_flag_turns_true_when_dead_rows_exist(monkeypatch):
    """有 dead 列時 alert 必須為 True，並給出重放查詢提示。"""
    from realtime.commission_outbox_worker import worker

    async def fake_sli():
        return {"oldest_pending_seconds": 0.0, "retry_exhausted_total": 3}

    monkeypatch.setattr(worker, "get_job_sli", fake_sli)

    class _U:
        user_id = "x"
        role = "admin"
        tenant_id = "t"

    result = await lifespan_health.get_health(user=_U())
    monkeypatch.undo()

    ob = result["commission_outbox"]
    assert ob["needs_manual_replay"] is True
    assert ob["replay_hint"] and "status = 'dead'" in ob["replay_hint"]
    assert result["summary"]["alert"] is True, "有 dead 事件時必須告警"
