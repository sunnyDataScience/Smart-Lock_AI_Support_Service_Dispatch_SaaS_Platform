"""audit NFR-Perf-009 / FR-API-05b：outbox 送達延遲 p95/p99 指標 + 派工分級 SLO。

補洞前 outbox worker 無任何 lag 度量儀器；FR-API-05b 再要求派工通知依 urgency 分級
（一般 P95≤30s、急件 P95≤15s）。此測試鎖定百分位計算 + 分級 SLO 判定（純函式，不碰 DB）。
"""

from __future__ import annotations

from realtime.line_push_outbox_worker import (
    _LAG_SAMPLES,
    get_outbox_lag_metrics,
    record_outbox_lag_seconds,
)


def test_lag_metrics_empty():
    _LAG_SAMPLES.clear()
    m = get_outbox_lag_metrics()
    assert m["count"] == 0
    assert m["p50_seconds"] is None and m["p95_seconds"] is None and m["p99_seconds"] is None
    # 派工分級桶存在且無樣本時 SLO 視為 met
    assert m["dispatch"]["normal"]["slo_seconds"] == 30.0
    assert m["dispatch"]["emergency"]["slo_seconds"] == 15.0
    assert m["dispatch"]["normal"]["slo_met"] is True


def test_lag_percentiles_overall():
    _LAG_SAMPLES.clear()
    for i in range(1, 101):  # 1..100 秒
        record_outbox_lag_seconds(float(i))
    m = get_outbox_lag_metrics()
    assert m["count"] == 100
    assert m["p50_seconds"] == 51.0    # idx=round(0.5*99)=50 → samples[50]=51
    assert m["p95_seconds"] == 95.0    # idx=round(0.95*99)=94 → samples[94]=95
    assert m["p99_seconds"] == 99.0


def test_dispatch_normal_slo_met_and_breach():
    _LAG_SAMPLES.clear()
    # 一般派工全部 ≤30s → SLO met
    for _ in range(50):
        record_outbox_lag_seconds(10.0, push_kind="tech_dispatch_assigned", urgency="normal")
    d = get_outbox_lag_metrics()["dispatch"]["normal"]
    assert d["count"] == 50 and d["slo_met"] is True and d["p95_seconds"] == 10.0
    # 追加一批 40s → P95 破 30s → SLO breach
    for _ in range(50):
        record_outbox_lag_seconds(40.0, push_kind="tech_dispatch_assigned", urgency="normal")
    d2 = get_outbox_lag_metrics()["dispatch"]["normal"]
    assert d2["p95_seconds"] > 30.0 and d2["slo_met"] is False


def test_dispatch_emergency_15s_slo():
    _LAG_SAMPLES.clear()
    for _ in range(20):
        record_outbox_lag_seconds(12.0, push_kind="tech_dispatch_assigned", urgency="emergency")
    d = get_outbox_lag_metrics()["dispatch"]["emergency"]
    assert d["count"] == 20 and d["slo_met"] is True    # 12s ≤ 15s
    record_outbox_lag_seconds(20.0, push_kind="tech_dispatch_assigned", urgency="emergency")
    # 混入 20s(>15s)後 P95 仍需看分佈；再灌多筆 20s 使 P95 破 15s
    for _ in range(20):
        record_outbox_lag_seconds(20.0, push_kind="tech_dispatch_assigned", urgency="emergency")
    d2 = get_outbox_lag_metrics()["dispatch"]["emergency"]
    assert d2["p95_seconds"] > 15.0 and d2["slo_met"] is False


def test_non_dispatch_not_counted_in_dispatch_bucket():
    _LAG_SAMPLES.clear()
    # 客戶推播（非派工 kind）不進派工桶
    record_outbox_lag_seconds(5.0, push_kind="work_order_assigned")
    m = get_outbox_lag_metrics()
    assert m["count"] == 1
    assert m["dispatch"]["normal"]["count"] == 0
    assert m["dispatch"]["emergency"]["count"] == 0
