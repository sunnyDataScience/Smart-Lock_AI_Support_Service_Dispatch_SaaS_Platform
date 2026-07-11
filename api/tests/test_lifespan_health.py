"""Lifespan Monitor Health — 8 monitor health check tests。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from routers.lifespan_health import _collect_monitors, _monitor_status


# ----------------------------- _monitor_status -----------------------------

def test_not_started_when_no_task():
    """task=None → not_started。"""
    mon = MagicMock()
    mon._task = None
    mon._stopping = asyncio.Event()
    mon._interval = 60
    status = _monitor_status(mon)
    assert status["state"] == "not_started"
    assert status["task_started"] is False


def test_running_when_task_active_and_not_stopping():
    """task done=False + stopping not set → running。"""
    mon = MagicMock()
    task = MagicMock()
    task.done.return_value = False
    mon._task = task
    stopping = asyncio.Event()
    mon._stopping = stopping
    mon._interval = 60
    status = _monitor_status(mon)
    assert status["state"] == "running"
    assert status["task_started"] is True
    assert status["task_done"] is False
    assert status["stopping_signal"] is False


def test_stopping_when_signal_set():
    mon = MagicMock()
    task = MagicMock()
    task.done.return_value = False
    mon._task = task
    stopping = asyncio.Event()
    stopping.set()
    mon._stopping = stopping
    mon._interval = 60
    status = _monitor_status(mon)
    assert status["state"] == "stopping"


def test_crashed_when_task_done_but_not_stopping():
    """task done=True 但 stopping 未 set → 異常終止 crashed。"""
    mon = MagicMock()
    task = MagicMock()
    task.done.return_value = True
    mon._task = task
    stopping = asyncio.Event()
    mon._stopping = stopping
    mon._interval = 60
    status = _monitor_status(mon)
    assert status["state"] == "crashed"


def test_interval_exposed():
    mon = MagicMock()
    mon._task = None
    mon._stopping = asyncio.Event()
    mon._interval = 3600
    status = _monitor_status(mon)
    assert status["interval_seconds"] == 3600


# ----------------------------- _collect_monitors -----------------------------

def test_collect_monitors_covers_all():
    """涵蓋所有 monitor name（CR-0166 R1 加 webhook_idem_cleanup / family_review_sla）。"""
    result = _collect_monitors()
    expected = {
        "inventory", "sla", "line_push_outbox",
        "reconciliation_exception", "dispute_escalation",
        "config_canary_advance", "statement_auto_approval",
        "gdpr_hard_delete",
        "webhook_idem_cleanup", "family_review_sla",
    }
    assert set(result.keys()) == expected


def test_collect_each_has_state_field():
    """每個 monitor 都應有 state 字段（即使 import_error）。"""
    result = _collect_monitors()
    for name, status in result.items():
        assert "state" in status, f"{name} missing state"


# ----------------------------- router -----------------------------

def test_router_has_1_endpoint():
    from routers import lifespan_health as mod
    assert len(mod.router.routes) == 1


def test_router_operation_id():
    from routers import lifespan_health as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert ids == {"getLifespanMonitorsHealth"}
