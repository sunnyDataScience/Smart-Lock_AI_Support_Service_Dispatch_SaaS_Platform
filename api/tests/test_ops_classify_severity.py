"""Ops Severity Classifier — pure function tests。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _classify():
    from scripts.ops.classify_severity import classify_severity
    return classify_severity


def _payload(total: int, by_state: dict) -> dict:
    return {"monitors": {}, "summary": {"total": total, "by_state": by_state}}


def test_all_running_info():
    assert _classify()(_payload(8, {"running": 8})) == "info"


def test_one_crashed_error():
    assert _classify()(_payload(8, {"running": 7, "crashed": 1})) == "error"


def test_half_crashed_critical():
    """crashed >= total/2 → critical。"""
    assert _classify()(_payload(8, {"running": 4, "crashed": 4})) == "critical"


def test_all_crashed_critical():
    assert _classify()(_payload(8, {"crashed": 8})) == "critical"


def test_import_error_critical():
    """部署檔損壞 → 重大事故。"""
    assert _classify()(_payload(8, {"running": 7, "import_error": 1})) == "critical"


def test_total_zero_critical():
    """lifespan not started → 重大事故。"""
    assert _classify()(_payload(0, {})) == "critical"


def test_stopping_warning():
    assert _classify()(_payload(8, {"running": 7, "stopping": 1})) == "warning"


def test_not_started_warning():
    """not_started 但 total > 0 (startup race) → warning。"""
    assert _classify()(_payload(8, {"running": 7, "not_started": 1})) == "warning"


def test_crashed_priority_over_stopping():
    """有 crashed 即使有 stopping 也是 error/critical（不被 stopping 降）。"""
    assert _classify()(_payload(8, {"crashed": 1, "stopping": 1, "running": 6})) == "error"


def test_import_error_priority_over_crashed():
    """import_error 為 critical 即使只 1 個，比 crashed=1 (error) 嚴重。"""
    assert _classify()(_payload(8, {"import_error": 1, "crashed": 1, "running": 6})) == "critical"


def test_empty_by_state_treated_info():
    """空 by_state 但 total > 0 (邊界) → info 不該誤判 critical。"""
    assert _classify()(_payload(3, {})) == "info"


def test_low_total_half_threshold():
    """total=2 → max(1, 1) = 1 → 1 crashed = critical（嚴格）"""
    # total=2 → max(1, 2//2=1) = 1 → crashed >= 1 入 critical
    assert _classify()(_payload(2, {"running": 1, "crashed": 1})) == "critical"


def test_total_1_one_crashed_critical():
    """total=1 唯一 monitor crashed → 系統全垮 critical。"""
    assert _classify()(_payload(1, {"crashed": 1})) == "critical"
