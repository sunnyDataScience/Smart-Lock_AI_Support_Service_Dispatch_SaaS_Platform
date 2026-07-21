"""audit NFR-Perf-009：outbox 送達延遲 p99 指標（outbox_lag_p99_seconds SLO）。

補洞前 outbox worker 無任何 lag/p99 度量儀器，SLO(p99 ≤ 30s) 無法佐證。
此測試鎖定新增的取樣 + 百分位計算（純函式，不碰 DB）。
"""

from __future__ import annotations

from realtime.line_push_outbox_worker import (
    _LAG_SAMPLES,
    get_outbox_lag_metrics,
    record_outbox_lag_seconds,
)


def test_lag_metrics_empty():
    _LAG_SAMPLES.clear()
    assert get_outbox_lag_metrics() == {
        "count": 0,
        "p50_seconds": None,
        "p99_seconds": None,
    }


def test_lag_percentiles():
    _LAG_SAMPLES.clear()
    for i in range(1, 101):  # 1..100 秒
        record_outbox_lag_seconds(float(i))
    m = get_outbox_lag_metrics()
    assert m["count"] == 100
    # p50 idx=round(0.5*99)=50 → samples[50]=51；p99 idx=round(0.99*99)=98 → samples[98]=99
    assert m["p50_seconds"] == 51.0
    assert m["p99_seconds"] == 99.0


def test_lag_ignores_negative_and_none():
    _LAG_SAMPLES.clear()
    record_outbox_lag_seconds(-5.0)
    record_outbox_lag_seconds(None)  # type: ignore[arg-type]
    record_outbox_lag_seconds(10.0)
    m = get_outbox_lag_metrics()
    assert m["count"] == 1
    assert m["p99_seconds"] == 10.0


def test_lag_window_bounded():
    _LAG_SAMPLES.clear()
    # maxlen=2000：塞 2500 筆，只留最後 2000
    for i in range(2500):
        record_outbox_lag_seconds(float(i))
    assert get_outbox_lag_metrics()["count"] == 2000
