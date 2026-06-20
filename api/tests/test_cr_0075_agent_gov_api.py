"""CR-0075 / TI-A12-01 + TI-A03-04 — AI 治理 trace + 對話後台（API 層，真 DB）。

A12-01：每個 AI 行為可追溯（prd_source+charter_rule+owner_decision_ref 三軸 provenance）。
A03-04：對話後台 list/detail。
既有 test_ai_governance_trace.py 用 FakeConn mock；本批改打真 saas.ai_decision_trace（更實）。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import ai_governance_trace_service as gov

TID = "00000000-0000-0000-0000-000000000001"


# ── decision_type 驗證（純邏輯）──
@pytest.mark.unit
def test_valid_decision_types_defined():
    from services.ai_governance_trace_service import _VALID_DECISION_TYPES
    assert {"reasoning", "tool_call", "output", "guardrail_block", "human_handoff"} <= _VALID_DECISION_TYPES


@pytest.mark.component
@pytest.mark.asyncio
async def test_log_decision_invalid_type_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as e:
        await gov.log_decision(tenant_id=TID, decision_type="nonsense", action_summary="x y z")
    assert e.value.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_log_decision_writes_provenance_and_filters():
    assert await db_module._ensure_conn()
    sess = "gov-" + uuid.uuid4().hex[:12]
    conv = str(uuid.uuid4())
    try:
        await gov.log_decision(
            tenant_id=TID, decision_type="output", action_summary="回覆客戶查詢",
            conversation_id=conv, agent_session_id=sess,
            prd_source="PRD-A05", charter_rule="no-final-quote", owner_decision_ref="Q012")
        await gov.log_decision(
            tenant_id=TID, decision_type="guardrail_block", action_summary="擋下報價數字",
            agent_session_id=sess, guardrail_triggered="price_redline", guardrail_action="block",
            prd_source="PRD-A05")
        # 依 conversation_id filter → 只回第一筆（provenance 三軸落了）
        out = await gov.list_traces(tenant_id=TID, conversation_id=conv)
        items = out.get("items") or out.get("traces") or []
        assert len(items) >= 1
        first = items[0]
        assert first.get("prd_source") == "PRD-A05"
        assert first.get("charter_rule") == "no-final-quote"
        # 依 prd_source filter → 兩筆都回
        out2 = await gov.list_traces(tenant_id=TID, prd_source="PRD-A05")
        sess_rows = [i for i in (out2.get("items") or out2.get("traces") or [])
                     if i.get("agent_session_id") == sess]
        assert len(sess_rows) >= 2
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.ai_decision_trace WHERE agent_session_id=%s", (sess,))


@pytest.mark.component
@pytest.mark.asyncio
async def test_trace_summary_aggregates():
    assert await db_module._ensure_conn()
    out = await gov.get_trace_summary(tenant_id=TID)
    # 聚合結構存在（by_decision_type / block_rate 等）
    assert isinstance(out, dict)
    assert any(k in out for k in ("by_decision_type", "total", "by_guardrail_action", "block_rate_pct"))


# ── A03-04 對話後台 list（cursor envelope）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_conversations_list_envelope():
    assert await db_module._ensure_conn()
    from services import conversation_service as cs
    out = await cs.list_conversations(tenant_id=TID, status=None, cursor=None, limit=5)
    assert "items" in out
    assert isinstance(out["items"], list)
    assert "has_more" in out or "next_cursor" in out or "cursor" in out
