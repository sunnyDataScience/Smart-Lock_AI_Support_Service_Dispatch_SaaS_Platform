"""Ops Alert PagerDuty — build_payload 純函式 tests。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _build():
    from scripts.ops.alert_pagerduty import build_payload
    return build_payload


def test_payload_includes_routing_key():
    payload = _build()(
        routing_key="abc123",
        source="staging",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    assert payload["routing_key"] == "abc123"
    assert payload["event_action"] == "trigger"


def test_payload_dedup_key_by_source():
    p1 = _build()(routing_key="k", source="staging",
                  health_payload={"monitors": {}, "summary": {}})
    p2 = _build()(routing_key="k", source="production",
                  health_payload={"monitors": {}, "summary": {}})
    assert p1["dedup_key"] != p2["dedup_key"]
    assert "staging" in p1["dedup_key"]
    assert "production" in p2["dedup_key"]


def test_payload_severity_passthrough():
    payload = _build()(
        routing_key="k", source="staging", severity="critical",
        health_payload={"monitors": {}, "summary": {}},
    )
    assert payload["payload"]["severity"] == "critical"


def test_payload_summary_lists_unhealthy():
    payload = _build()(
        routing_key="k", source="staging",
        health_payload={
            "monitors": {
                "inventory": {"state": "running"},
                "gdpr_hard_delete": {"state": "crashed"},
                "sla": {"state": "stopping"},
            },
            "summary": {"total": 3, "by_state": {"running": 1, "crashed": 1, "stopping": 1}},
        },
    )
    summary = payload["payload"]["summary"]
    assert "gdpr_hard_delete=crashed" in summary
    assert "sla=stopping" in summary
    # running 不該出現在 unhealthy
    assert "inventory=running" not in summary


def test_payload_custom_details_complete():
    payload = _build()(
        routing_key="k", source="prod",
        health_payload={
            "monitors": {
                "a": {"state": "running"},
                "b": {"state": "crashed"},
            },
            "summary": {"total": 2, "by_state": {"running": 1, "crashed": 1}},
        },
    )
    details = payload["payload"]["custom_details"]
    assert details["total_monitors"] == 2
    assert details["unhealthy_count"] == 1
    assert details["unhealthy_list"] == ["b: crashed"]
    assert "runbook" in details


def test_payload_summary_truncated_at_1024():
    """大量 monitors → summary 截斷 1024 字元。"""
    monitors = {f"m{i}": {"state": "crashed"} for i in range(100)}
    payload = _build()(
        routing_key="k", source="staging",
        health_payload={
            "monitors": monitors,
            "summary": {"total": 100, "by_state": {"crashed": 100}},
        },
    )
    assert len(payload["payload"]["summary"]) <= 1024


def test_payload_max_5_unhealthy_in_summary():
    """summary text 只顯示前 5 個 unhealthy。"""
    monitors = {f"m{i}": {"state": "crashed"} for i in range(10)}
    payload = _build()(
        routing_key="k", source="staging",
        health_payload={
            "monitors": monitors,
            "summary": {"total": 10, "by_state": {"crashed": 10}},
        },
    )
    summary = payload["payload"]["summary"]
    # 10 unhealthy 但 summary 只列前 5 (m0-m4)
    assert summary.count("=crashed") == 5
    # custom_details 全列
    assert len(payload["payload"]["custom_details"]["unhealthy_list"]) == 10


def test_payload_required_pd_fields():
    """PagerDuty Events API v2 required fields。"""
    payload = _build()(
        routing_key="k", source="staging",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    assert "routing_key" in payload
    assert "event_action" in payload
    assert "payload" in payload
    inner = payload["payload"]
    assert "summary" in inner
    assert "source" in inner
    assert "severity" in inner
