"""CR-0019 Stage 1 — SLA gate 純函式 unit tests。

驗證 loadtest/sla.py 的 CSV 解析與門檻邏輯：
- 完美 row 全 pass
- p95 GET 超門檻 → breach 列出 "p95 GET ..."
- p95 POST 超門檻 → breach
- error rate 超 1% → breach
- throughput 低於 100 r/s → breach
- 自訂 thresholds 套用正確

不依賴 Locust 安裝，純對 CSV 邏輯。
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

# 把 repo root 加入 sys.path 讓 import loadtest.sla 可運作
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loadtest.sla import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    SlaResult,
    SlaThresholds,
    evaluate_csv,
)


def _write_csv(tmp_path, rows: list[dict]) -> str:
    """寫一份 Locust stats CSV 給 evaluate_csv 讀。"""
    path = tmp_path / "stats.csv"
    fields = [
        "Type", "Name", "Request Count", "Failure Count",
        "Median Response Time", "Average Response Time",
        "Min Response Time", "Max Response Time",
        "Average Content Size", "Requests/s", "Failures/s",
        "50%", "66%", "75%", "80%", "90%", "95%", "98%",
        "99%", "99.9%", "99.99%", "100%",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k, "") for k in fields}
            w.writerow(row)
    return str(path)


def _agg(*, requests: int, failures: int, rps: float) -> dict:
    return {
        "Type": "", "Name": "Aggregated",
        "Request Count": requests, "Failure Count": failures,
        "Requests/s": rps,
    }


def _endpoint(*, type_: str, name: str, p95: float) -> dict:
    return {
        "Type": type_, "Name": name,
        "Request Count": 100, "Failure Count": 0,
        "Requests/s": 1, "95%": p95,
    }


# ----------------------------- happy path -----------------------------

def test_evaluate_csv_all_pass(tmp_path):
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=300),
        _endpoint(type_="POST", name="POST :accept", p95=800),
        _agg(requests=10000, failures=50, rps=150),
    ])
    result = evaluate_csv(csv_path)
    assert isinstance(result, SlaResult)
    assert result.passed is True
    assert result.breaches == []
    assert result.summary["error_rate_pct"] == 0.5
    assert result.summary["throughput_rps"] == 150
    assert result.summary["p95_get_ms"] == 300
    assert result.summary["p95_post_ms"] == 800


# ----------------------------- 個別 breach -----------------------------

def test_evaluate_csv_p95_get_breach(tmp_path):
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=600),  # > 500
        _endpoint(type_="POST", name="POST :accept", p95=800),
        _agg(requests=10000, failures=0, rps=150),
    ])
    result = evaluate_csv(csv_path)
    assert result.passed is False
    assert any("p95 GET" in b for b in result.breaches)


def test_evaluate_csv_p95_post_breach(tmp_path):
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=300),
        _endpoint(type_="POST", name="POST :accept", p95=1500),  # > 1000
        _agg(requests=10000, failures=0, rps=150),
    ])
    result = evaluate_csv(csv_path)
    assert result.passed is False
    assert any("p95 POST" in b for b in result.breaches)


def test_evaluate_csv_patch_treated_as_post(tmp_path):
    """PATCH/DELETE 同 POST 走 p95_post 門檻。"""
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="PATCH", name="PATCH /schedule", p95=1200),
        _agg(requests=100, failures=0, rps=150),
    ])
    result = evaluate_csv(csv_path)
    assert any("p95 POST" in b for b in result.breaches)


def test_evaluate_csv_error_rate_breach(tmp_path):
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=300),
        _agg(requests=1000, failures=20, rps=150),  # 2% > 1%
    ])
    result = evaluate_csv(csv_path)
    assert result.passed is False
    assert any("error rate" in b for b in result.breaches)


def test_evaluate_csv_throughput_breach(tmp_path):
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=300),
        _agg(requests=10000, failures=0, rps=50),  # < 100
    ])
    result = evaluate_csv(csv_path)
    assert result.passed is False
    assert any("throughput" in b for b in result.breaches)


def test_evaluate_csv_multiple_breaches(tmp_path):
    """同時 GET / POST / error / throughput 全爆 → breach 列 4 條。"""
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="x", p95=999),
        _endpoint(type_="POST", name="y", p95=9999),
        _agg(requests=1000, failures=100, rps=10),
    ])
    result = evaluate_csv(csv_path)
    assert result.passed is False
    assert len(result.breaches) == 4


# ----------------------------- 自訂 thresholds -----------------------------

def test_custom_thresholds_more_strict(tmp_path):
    """tightening 300ms GET → 400ms p95 變 breach。"""
    csv_path = _write_csv(tmp_path, [
        _endpoint(type_="GET", name="GET pool", p95=400),
        _agg(requests=1000, failures=0, rps=150),
    ])
    strict = SlaThresholds(p95_get_ms=300, p95_post_ms=1000,
                            error_rate_pct=1.0, min_throughput_rps=100.0)
    result = evaluate_csv(csv_path, strict)
    assert result.passed is False


def test_default_thresholds_values_unchanged():
    """sanity — HD-2 保守門檻不該被無意改。"""
    assert DEFAULT_THRESHOLDS.p95_get_ms == 500
    assert DEFAULT_THRESHOLDS.p95_post_ms == 1000
    assert DEFAULT_THRESHOLDS.error_rate_pct == 1.0
    assert DEFAULT_THRESHOLDS.min_throughput_rps == 100.0


# ----------------------------- 邊界 -----------------------------

def test_evaluate_csv_empty_no_requests(tmp_path):
    """無 row → 不該 ZeroDivisionError。"""
    csv_path = _write_csv(tmp_path, [_agg(requests=0, failures=0, rps=0)])
    result = evaluate_csv(csv_path)
    # error_rate=0, throughput=0 → 只有 throughput breach
    assert result.summary["error_rate_pct"] == 0.0
    # throughput 0 < 100 → 1 breach
    assert any("throughput" in b for b in result.breaches)


def test_evaluate_csv_p95_na_string_treated_as_zero(tmp_path):
    """Locust 偶爾把空列 95% 寫成 'N/A' — 應視為 0 不炸。"""
    csv_path = _write_csv(tmp_path, [
        {"Type": "GET", "Name": "rare", "95%": "N/A",
         "Request Count": 1, "Failure Count": 0, "Requests/s": 1},
        _agg(requests=1, failures=0, rps=150),
    ])
    result = evaluate_csv(csv_path)
    # N/A → 0ms → 不 breach
    assert result.summary["p95_get_ms"] == 0.0
