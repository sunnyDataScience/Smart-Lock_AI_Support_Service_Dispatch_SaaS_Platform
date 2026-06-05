"""AI Governance Trace — FR-0050 MVP service + router tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import ai_governance_trace_service as svc


class FakeCur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    async def fetchone(self):
        return self._row

    async def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = (
            self._results[self._idx] if self._idx < len(self._results)
            else FakeCur()
        )
        self._idx += 1
        return result


# ----------------------------- log_decision -----------------------------

@pytest.mark.asyncio
async def test_log_decision_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=("trace-1", now)),
    ])

    result = await svc.log_decision(
        tenant_id="t1",
        decision_type="reasoning",
        action_summary="LLM 推理：客戶要求改期",
        conversation_id="conv-1",
        prd_source="docs/_source/02-ai-chatbot-sync.md#a-m12",
        charter_rule="ADR-0028 §A.1",
    )
    assert result["id"] == "trace-1"
    assert result["decision_type"] == "reasoning"


@pytest.mark.asyncio
async def test_log_decision_invalid_type(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.log_decision(
            tenant_id="t1", decision_type="invalid_kind",
            action_summary="x",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_log_decision_invalid_guardrail_action(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_decision(
            tenant_id="t1", decision_type="reasoning",
            action_summary="x reasoning",
            guardrail_action="not_a_valid_action",
        )


@pytest.mark.asyncio
async def test_log_decision_short_summary(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.log_decision(
            tenant_id="t1", decision_type="reasoning",
            action_summary="x",  # < 3
        )
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- list_traces -----------------------------

@pytest.mark.asyncio
async def test_list_traces_with_filters(monkeypatch):
    """SQL 應含 conversation/work_order/decision_type/date filter clauses。"""
    import core.db as db_module
    from datetime import date

    captured = {"sql": None, "args": None}

    class CapConn:
        async def execute(self, sql, args):
            captured["sql"] = sql
            captured["args"] = args
            class C:
                async def fetchall(self):
                    return []
            return C()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = CapConn()

    await svc.list_traces(
        tenant_id="t1", decision_type="tool_call",
        conversation_id="conv-1",
        work_order_id="wo-1",
        start_date=date(2026, 5, 1), end_date=date(2026, 6, 1),
    )
    sql = captured["sql"]
    assert "decision_type = %s" in sql
    assert "conversation_id = %s::uuid" in sql
    assert "work_order_id = %s::uuid" in sql
    assert "BETWEEN" in sql


@pytest.mark.asyncio
async def test_list_traces_invalid_decision_type(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.list_traces(tenant_id="t1", decision_type="bogus")
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_traces_limit_validation(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.list_traces(tenant_id="t1", limit=0)
    with pytest.raises(ApiError):
        await svc.list_traces(tenant_id="t1", limit=501)


# ----------------------------- get_trace_summary -----------------------------

@pytest.mark.asyncio
async def test_summary_aggregates_by_type_action_version(monkeypatch):
    """3 query 結果 → summary 結構正確。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. by decision_type
        FakeCur(rows=[("reasoning", 100), ("tool_call", 50), ("guardrail_block", 5)]),
        # 2. by guardrail_action
        FakeCur(rows=[("block", 5), ("warn", 10)]),
        # 3. by agent_version
        FakeCur(rows=[("gemini-1.5-pro", 120), ("gpt-4o", 35)]),
    ])

    result = await svc.get_trace_summary(tenant_id="t1")
    assert result["totals"]["total_decisions"] == 155
    assert result["totals"]["block_count"] == 5
    # block_rate = 5/155 = 3.23%
    assert result["totals"]["block_rate_pct"] == 3.23
    assert result["by_decision_type"]["reasoning"] == 100
    assert result["by_guardrail_action"]["block"] == 5
    assert result["by_agent_version"]["gpt-4o"] == 35


@pytest.mark.asyncio
async def test_summary_empty_no_div_by_zero(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[]), FakeCur(rows=[]), FakeCur(rows=[]),
    ])

    result = await svc.get_trace_summary(tenant_id="t1")
    assert result["totals"]["total_decisions"] == 0
    assert result["totals"]["block_rate_pct"] == 0.0


# ----------------------------- router -----------------------------

def test_router_has_3_endpoints():
    from routers import ai_governance_trace_v2 as mod
    assert len(mod.router.routes) == 3


def test_router_expected_operation_ids():
    from routers import ai_governance_trace_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "logAiDecisionTrace",
        "listAiDecisionTraces",
        "getAiGovernanceTraceSummary",
    }
    assert ids == expected
