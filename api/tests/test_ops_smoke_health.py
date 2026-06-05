"""Ops Smoke Script — evaluate() 純函式 tests (HTTP 部分 mock)。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 把 repo root 加 sys.path 讓 import scripts/* 可運作
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _eval():
    from scripts.ops.check_monitors_health import evaluate
    return evaluate


def test_all_running_exit_0():
    payload = {
        "monitors": {
            "inventory": {"state": "running"},
            "sla": {"state": "running"},
        },
        "summary": {"total": 2, "by_state": {"running": 2}, "all_running": True},
    }
    code, msg = _eval()(payload)
    assert code == 0
    assert "ALL 2 monitors running" in msg


def test_one_crashed_exit_1():
    payload = {
        "monitors": {
            "inventory": {"state": "running"},
            "gdpr_hard_delete": {"state": "crashed"},
        },
        "summary": {
            "total": 2,
            "by_state": {"running": 1, "crashed": 1},
            "all_running": False,
        },
    }
    code, msg = _eval()(payload)
    assert code == 1
    assert "gdpr_hard_delete" in msg
    assert "crashed" in msg


def test_import_error_exit_1():
    payload = {
        "monitors": {
            "inventory": {"state": "running"},
            "foo": {"state": "import_error"},
        },
        "summary": {
            "total": 2,
            "by_state": {"running": 1, "import_error": 1},
            "all_running": False,
        },
    }
    code, msg = _eval()(payload)
    assert code == 1
    assert "import_error" in msg


def test_empty_total_zero_treated_unhealthy():
    """total=0 即使 all_running=True 也不該認為 healthy。"""
    payload = {
        "monitors": {},
        "summary": {"total": 0, "by_state": {}, "all_running": True},
    }
    code, _msg = _eval()(payload)
    # all_running=true + total=0 → not healthy
    assert code == 1


def test_multiple_unhealthy_listed():
    """多個 unhealthy 都應列在 message。"""
    payload = {
        "monitors": {
            "a": {"state": "running"},
            "b": {"state": "crashed"},
            "c": {"state": "stopping"},
            "d": {"state": "not_started"},
        },
        "summary": {
            "total": 4,
            "by_state": {"running": 1, "crashed": 1, "stopping": 1, "not_started": 1},
            "all_running": False,
        },
    }
    code, msg = _eval()(payload)
    assert code == 1
    assert "b: crashed" in msg
    assert "c: stopping" in msg
    assert "d: not_started" in msg
