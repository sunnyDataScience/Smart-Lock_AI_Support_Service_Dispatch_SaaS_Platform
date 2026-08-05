"""NFR-Perf-009：Outbox → 事件骨幹 lag 的 p99/p99.9（CR-0209 TC-PERF-05）。

WHY：NFR-Perf-009（`05_NFR.md:49`）量的是「Outbox → **事件骨幹** lag」，
p99 ≤ 30s / p99.9 ≤ 2min；`:231` 把它與 Kafka consumer lag 綁定，證實
「事件骨幹」＝Kafka。而全系統唯一走事件骨幹的 outbox 是
`commission_event_outbox`（commission_outbox_worker → publish_event → Kafka），
它此前**零 lag 取樣**。

唯一有 percentile 的是 `line_push_outbox_worker`——但那個 outbox **不走事件骨幹**
（它是 LINE 推播），且它的 p95 對應的是 FR-API-05b 的派工 SLO，是另一條需求。
也就是 **p99 一直量在錯的 outbox 上**。

`get_job_sli()` 的 `oldest_pending_seconds` 是瞬時 gauge，算不出分佈——
p99/p99.9 需要逐筆樣本。
"""
from __future__ import annotations

import pytest

from realtime import commission_outbox_worker as w


@pytest.fixture(autouse=True)
def _clear_samples():
    w._LAG_SAMPLES.clear()
    yield
    w._LAG_SAMPLES.clear()


def test_empty_window_reports_no_percentiles_and_passes_slo():
    m = w.get_backbone_lag_metrics()
    assert m["count"] == 0
    assert m["p99_seconds"] is None
    assert m["slo_met"] is True, "無樣本時不應判定為破線（那會製造假告警）"


def test_percentiles_and_slo_thresholds():
    for v in range(1, 101):          # 1..100 秒
        w.record_backbone_lag_seconds(float(v))
    m = w.get_backbone_lag_metrics()
    assert m["count"] == 100
    # 採 nearest-rank 慣例（idx = round(p/100 * (n-1))），不硬編單一數字——
    # 這裡要驗的是「分位數有算出來且單調」，不是綁死某個取整策略。
    assert 45.0 <= m["p50_seconds"] <= 55.0
    assert m["p99_seconds"] >= 95.0
    assert m["p50_seconds"] < m["p99_seconds"] <= m["p999_seconds"]
    assert m["slo_p99_seconds"] == 30.0
    assert m["slo_p999_seconds"] == 120.0
    assert m["slo_met"] is False, "p99 遠超 30s 卻判定達標"


def test_within_slo_reports_met():
    for _ in range(200):
        w.record_backbone_lag_seconds(2.0)
    assert w.get_backbone_lag_metrics()["slo_met"] is True


def test_invalid_samples_ignored():
    """負值與 None 忽略——量測不可因髒資料而失真或拋錯。"""
    w.record_backbone_lag_seconds(None)
    w.record_backbone_lag_seconds(-1.0)
    assert w.get_backbone_lag_metrics()["count"] == 0


def test_window_is_bounded():
    """滾動視窗有上界，長跑不會無限吃記憶體。"""
    assert w._LAG_SAMPLES.maxlen is not None
    for i in range(w._LAG_SAMPLES.maxlen + 500):
        w.record_backbone_lag_seconds(float(i % 10))
    assert len(w._LAG_SAMPLES) == w._LAG_SAMPLES.maxlen
