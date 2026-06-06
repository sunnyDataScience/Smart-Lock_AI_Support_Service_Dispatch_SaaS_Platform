"""P4 Stage 7 v1 metrics snapshot + aggregate — pure function tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── snapshot ─────────────────────────────────────────────────────────

def _snapshot_mod():
    from scripts.ops import snapshot_v1_metrics
    return snapshot_v1_metrics


def test_write_snapshot_creates_day_dir(tmp_path):
    mod = _snapshot_mod()
    snap = {
        "captured_at": "2026-06-06T10:30:00+00:00",
        "captured_at_epoch": int(
            datetime(2026, 6, 6, 10, 30, tzinfo=timezone.utc).timestamp()
        ),
        "endpoints": {},
    }
    out = mod.write_snapshot(snap, tmp_path)
    assert out.exists()
    assert out.parent.name == "2026-06-06"
    assert out.name == "10-30.json"
    loaded = json.loads(out.read_text())
    assert loaded["captured_at"] == "2026-06-06T10:30:00+00:00"


def test_summarize_extracts_total_hits():
    mod = _snapshot_mod()
    snap = {
        "endpoints": {
            "v1_metrics": {"data": {
                "items": [
                    {"path": "/api/v1/foo", "count": 5},
                    {"path": "/api/v1/bar", "count": 10},
                ],
            }},
            "v1_inventory": {"data": {"total_endpoints": 41}},
            "no_traffic": {"data": {"total_routes": 30}},
        },
    }
    result = mod.summarize(snap)
    assert "v1_hits=15" in result
    assert "v1_endpoints=41" in result
    assert "no_traffic_routes=30" in result


def test_summarize_empty_metrics():
    mod = _snapshot_mod()
    snap = {"endpoints": {}}
    result = mod.summarize(snap)
    assert "v1_hits=0" in result


# ─── aggregate ────────────────────────────────────────────────────────

def _agg_mod():
    from scripts.ops import aggregate_v1_metrics
    return aggregate_v1_metrics


def _make_snapshot(epoch: int, items: list[dict], inventory: list[dict] | None = None):
    return {
        "captured_at_epoch": epoch,
        "endpoints": {
            "v1_metrics": {
                "status": 200,
                "data": {"items": items},
            },
            "v1_inventory": {
                "status": 200,
                "data": {"items": inventory or []},
            },
        },
    }


def test_aggregate_sums_hits_per_endpoint():
    mod = _agg_mod()
    base = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    snaps = [
        _make_snapshot(base + 0, [
            {"method": "GET", "path": "/api/v1/a", "count": 5},
        ]),
        _make_snapshot(base + 3600, [
            {"method": "GET", "path": "/api/v1/a", "count": 3},
            {"method": "POST", "path": "/api/v1/b", "count": 2},
        ]),
    ]
    agg = mod.aggregate(snaps)
    stats = agg["endpoint_stats"]
    assert stats["GET /api/v1/a"]["total_hits"] == 8
    assert stats["GET /api/v1/a"]["max_hourly_hits"] == 5
    assert stats["POST /api/v1/b"]["total_hits"] == 2


def test_classify_for_stage7_separates_zero_vs_active():
    mod = _agg_mod()
    base = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    snaps = [
        _make_snapshot(base, [
            {"method": "GET", "path": "/api/v1/active", "count": 7},
            {"method": "GET", "path": "/api/v1/zero", "count": 0},
        ]),
    ]
    agg = mod.aggregate(snaps)
    safe, keep = mod.classify_for_stage7(agg)
    safe_keys = [k for k, _ in safe]
    keep_keys = [k for k, _ in keep]
    assert "GET /api/v1/zero" in safe_keys
    assert "GET /api/v1/active" in keep_keys


def test_render_report_full_green_recommends_delete():
    mod = _agg_mod()
    base = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    snaps = [
        _make_snapshot(base, [
            {"method": "GET", "path": "/api/v1/zero1", "count": 0},
            {"method": "GET", "path": "/api/v1/zero2", "count": 0},
        ]),
    ]
    agg = mod.aggregate(snaps)
    report = mod.render_report(agg, window_days=30)
    assert "✅" in report
    assert "建議業主簽 Stage 7" in report


def test_render_report_full_red_recommends_extend():
    mod = _agg_mod()
    base = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    snaps = [
        _make_snapshot(base, [
            {"method": "GET", "path": "/api/v1/busy", "count": 100},
        ]),
    ]
    agg = mod.aggregate(snaps)
    report = mod.render_report(agg, window_days=30)
    assert "延期 Stage 7" in report or "❌" in report


def test_render_report_mixed_state_recommends_phased():
    mod = _agg_mod()
    base = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    snaps = [
        _make_snapshot(base, [
            {"method": "GET", "path": "/api/v1/busy", "count": 50},
            {"method": "GET", "path": "/api/v1/zero", "count": 0},
        ]),
    ]
    agg = mod.aggregate(snaps)
    report = mod.render_report(agg, window_days=30)
    assert "⚠️" in report
    assert "階段性刪除" in report


def test_load_snapshots_filters_by_window(tmp_path):
    mod = _agg_mod()
    # Old snapshot (60 day ago)
    old_dir = tmp_path / "2026-04-01"
    old_dir.mkdir()
    old_epoch = int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp())
    (old_dir / "00-00.json").write_text(json.dumps({
        "captured_at_epoch": old_epoch,
        "endpoints": {},
    }))
    # Recent snapshot (today)
    recent_dir = tmp_path / "2026-06-06"
    recent_dir.mkdir()
    recent_epoch = int(datetime(2026, 6, 6, tzinfo=timezone.utc).timestamp())
    (recent_dir / "00-00.json").write_text(json.dumps({
        "captured_at_epoch": recent_epoch,
        "endpoints": {},
    }))
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    snaps = mod.load_snapshots(tmp_path, since)
    assert len(snaps) == 1
    assert snaps[0]["captured_at_epoch"] == recent_epoch
