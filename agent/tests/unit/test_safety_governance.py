"""Unit tests for WBS 3.0 — L6 Safety Gate + L3 Governance."""

import pytest

from harness.safety.gate import (
    _check_dangerous_keywords,
    _check_pii,
    _check_sentiment_and_emergency,
    safety_gate,
)
from harness.governance.registry import ToolRegistry, RiskLevel


# ── Safety Gate tests ──

@pytest.fixture(autouse=True)
def enable_safety(monkeypatch):
    monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: True)


class TestDangerousKeywords:
    def test_detects_dangerous_keyword(self, monkeypatch):
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": ["拆開電路板", "剪斷電線"]}},
        )
        risks = _check_dangerous_keywords("我想拆開電路板看看")
        assert len(risks) == 1
        assert risks[0]["keyword"] == "拆開電路板"

    def test_no_dangerous_keyword(self, monkeypatch):
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": ["拆開電路板"]}},
        )
        risks = _check_dangerous_keywords("我的鎖壞了")
        assert risks == []


class TestPII:
    def test_detects_phone(self):
        risks = _check_pii("我的電話是 0912-345-678")
        assert any(r["pii_type"] == "phone" for r in risks)

    def test_detects_email(self):
        risks = _check_pii("請寄到 test@example.com")
        assert any(r["pii_type"] == "email" for r in risks)

    def test_no_pii(self):
        risks = _check_pii("我的鎖壞了")
        assert risks == []


class TestSentimentEmergency:
    def test_red_code_locked_out(self):
        result = _check_sentiment_and_emergency("我被鎖在外面，小孩在裡面")
        assert result["red_code"] is True
        assert result["sentiment_level"] == "emergency"

    def test_high_risk_complaint(self):
        result = _check_sentiment_and_emergency("太離譜了，我要投訴")
        assert result["escalation_required"] is True

    def test_normal_message(self):
        result = _check_sentiment_and_emergency("我的指紋按了沒反應")
        assert result["red_code"] is False
        assert result["escalation_required"] is False
        assert result["sentiment_level"] == "normal"


@pytest.mark.asyncio
async def test_safety_gate_full_flow(monkeypatch):
    monkeypatch.setattr(
        "harness.safety.gate.HARNESS_CONFIG",
        {"safety": {"dangerous_instruction_keywords": ["拆開電路板"]}},
    )
    state = {"question": "我想拆開電路板，電話 0912345678"}
    result = await safety_gate(state)

    safety = result["safety"]
    assert safety["requires_approval"] is True
    assert any(r["risk_type"] == "dangerous_instruction" for r in safety["flagged_risks"])
    assert any(r["risk_type"] == "pii_exposure" for r in safety["flagged_risks"])
    assert result["history"] == ["safety_gate:flagged"]


@pytest.mark.asyncio
async def test_safety_gate_skip_when_disabled(monkeypatch):
    monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: False)
    result = await safety_gate({"question": "拆開電路板"})
    assert result == {"history": ["safety_gate:skip"]}


# ── Governance Registry tests ──

class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        tools = {"db_video": "mock_tool_1", "db_manuals": "mock_tool_2", "transfer_to_human": "mock_tool_3"}
        risk_config = {"db_video": "read", "db_manuals": "read", "transfer_to_human": "escalate"}
        return ToolRegistry(tools, risk_config)

    def test_get_risk_level(self, registry):
        assert registry.get_risk_level("db_video") == RiskLevel.READ
        assert registry.get_risk_level("transfer_to_human") == RiskLevel.ESCALATE

    def test_get_risk_level_unknown_defaults_read(self, registry):
        assert registry.get_risk_level("nonexistent") == RiskLevel.READ

    def test_get_tools_for_agent(self, registry):
        tools = registry.get_tools_for_agent(["db_video", "transfer_to_human"])
        assert len(tools) == 2

    def test_get_tools_for_agent_missing(self, registry):
        tools = registry.get_tools_for_agent(["db_video", "nonexistent"])
        assert len(tools) == 1

    def test_get_tools_by_risk(self, registry):
        read_only = registry.get_tools_by_risk(RiskLevel.READ)
        assert len(read_only) == 2  # db_video, db_manuals
        all_tools = registry.get_tools_by_risk(RiskLevel.ESCALATE)
        assert len(all_tools) == 3
