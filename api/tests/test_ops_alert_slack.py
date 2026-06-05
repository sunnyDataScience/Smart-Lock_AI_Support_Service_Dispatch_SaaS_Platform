"""Ops Alert Slack — build_payload 純函式 tests。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _build():
    from scripts.ops.alert_slack import build_payload
    return build_payload


def test_payload_uses_block_kit():
    """Slack 用 Block Kit format。"""
    payload = _build()(
        source="staging",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    assert "blocks" in payload
    assert isinstance(payload["blocks"], list)


def test_payload_header_includes_source_and_count():
    payload = _build()(
        source="production",
        health_payload={
            "monitors": {
                "a": {"state": "running"},
                "b": {"state": "crashed"},
            },
            "summary": {"total": 2, "by_state": {"running": 1, "crashed": 1}},
        },
    )
    header_text = payload["blocks"][0]["text"]["text"]
    assert "production" in header_text
    assert "1/2" in header_text


def test_payload_severity_emoji_mapping():
    """4 severity 各對應 emoji。"""
    for sev, expected_emoji in [
        ("critical", ":rotating_light:"),
        ("error", ":red_circle:"),
        ("warning", ":warning:"),
        ("info", ":information_source:"),
    ]:
        payload = _build()(
            source="staging", severity=sev,
            health_payload={"monitors": {}, "summary": {"total": 0}},
        )
        header = payload["blocks"][0]["text"]["text"]
        assert expected_emoji in header, f"{sev} missing {expected_emoji}"


def test_payload_unhealthy_section_listed():
    payload = _build()(
        source="staging",
        health_payload={
            "monitors": {
                "running_one": {"state": "running"},
                "broken_one": {"state": "crashed"},
                "stopping_one": {"state": "stopping"},
            },
            "summary": {"total": 3, "by_state": {"running": 1, "crashed": 1, "stopping": 1}},
        },
    )
    # 找 "Unhealthy monitors" section
    unhealthy_blocks = [
        b for b in payload["blocks"]
        if b.get("type") == "section"
        and "Unhealthy monitors" in b.get("text", {}).get("text", "")
    ]
    assert len(unhealthy_blocks) == 1
    text = unhealthy_blocks[0]["text"]["text"]
    assert "broken_one" in text
    assert "stopping_one" in text
    # running_one 不該在 unhealthy 區
    assert "running_one" not in text


def test_payload_truncated_at_10_listed_more_in_text():
    """大量 unhealthy → 列前 10 + 「and N more」。"""
    monitors = {f"m{i}": {"state": "crashed"} for i in range(15)}
    payload = _build()(
        source="staging",
        health_payload={
            "monitors": monitors,
            "summary": {"total": 15, "by_state": {"crashed": 15}},
        },
    )
    unhealthy_blocks = [
        b for b in payload["blocks"]
        if b.get("type") == "section"
        and "Unhealthy monitors" in b.get("text", {}).get("text", "")
    ]
    text = unhealthy_blocks[0]["text"]["text"]
    assert "and 5 more" in text


def test_payload_no_unhealthy_section_when_empty():
    """無 unhealthy → 不該有 Unhealthy section。"""
    payload = _build()(
        source="staging",
        health_payload={
            "monitors": {"a": {"state": "running"}},
            "summary": {"total": 1, "by_state": {"running": 1}},
        },
    )
    unhealthy_blocks = [
        b for b in payload["blocks"]
        if b.get("type") == "section"
        and "Unhealthy monitors" in b.get("text", {}).get("text", "")
    ]
    assert unhealthy_blocks == []


def test_payload_channel_override():
    payload = _build()(
        source="staging", channel="#ops-alerts",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    assert payload["channel"] == "#ops-alerts"


def test_payload_no_channel_when_not_specified():
    payload = _build()(
        source="staging",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    assert "channel" not in payload


def test_payload_runbook_reference_in_context():
    """context block 應含 runbook reference。"""
    payload = _build()(
        source="staging",
        health_payload={"monitors": {}, "summary": {"total": 0}},
    )
    context_blocks = [b for b in payload["blocks"] if b.get("type") == "context"]
    assert len(context_blocks) >= 1
    text = context_blocks[0]["elements"][0]["text"]
    assert "Runbook" in text
    assert "background-monitors-runbook.md" in text
