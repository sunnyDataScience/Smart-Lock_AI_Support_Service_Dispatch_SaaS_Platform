"""transfer_to_human 工具 + EscalationStore 測試 — 離線,不打 API。"""

import asyncio

from lockcore.agent.tools.context import RequestContext
from lockcore.agent.tools.transfer import TransferToHumanTool, _is_explicit_transfer_request
from lockcore.agent.user_memory import EscalationStore, MemoryStore


def _tool(mem=None, esc=None, tenant="locksmart"):
    return TransferToHumanTool(memory_store=mem, escalation_store=esc, tenant=tenant)


def _set(tool, user_id, user_input=""):
    tool.set_context(
        RequestContext(channel="cli", chat_id=user_id, metadata={"user_input": user_input})
    )


def test_name_and_policy_in_description():
    t = _tool()
    assert t.name == "transfer_to_human"
    d = t.description
    assert "最後手段" in d
    assert "原封不動" in d          # 回覆規定
    assert "報價" in d              # 金錢白名單
    assert "先試答" in d or "禁止" in d


def test_is_explicit_keyword_detection():
    assert _is_explicit_transfer_request("我要找真人") is True
    assert _is_explicit_transfer_request("這台多少錢") is True       # 金錢視為 explicit
    assert _is_explicit_transfer_request("怎麼改密碼") is False
    assert _is_explicit_transfer_request("") is False


def test_execute_logs_escalation_and_renders_template():
    mem = MemoryStore(":memory:")
    esc = EscalationStore(":memory:")
    mem.add("locksmart", "u1", "fact", "客人的鎖是 Dormakaba AS701")
    mem.add("locksmart", "u1", "profile", "電話 0912-345-678")

    t = _tool(mem=mem, esc=esc)
    _set(t, "u1", user_input="我要找真人專員")
    out = asyncio.run(t.execute(reason="客戶明確要求真人"))

    # 模板有填入 facts
    assert "Dormakaba AS701" in out
    assert "0912-345-678" in out
    # escalation 落地 + is_explicit 正確
    recs = esc.list_for_user("locksmart", "u1")
    assert len(recs) == 1
    assert recs[0].is_explicit is True
    assert recs[0].reason == "客戶明確要求真人"
    assert "Dormakaba AS701" in recs[0].facts_snapshot["facts_block"]


def test_execute_graceful_without_stores():
    """無 memory/escalation store 也不崩,回模板的『尚未掌握』版本。"""
    t = _tool(mem=None, esc=None)
    _set(t, "anon", user_input="幫我轉接")
    out = asyncio.run(t.execute(reason="測試"))
    assert "尚未掌握" in out


def test_execute_no_facts_uses_placeholder():
    mem = MemoryStore(":memory:")
    esc = EscalationStore(":memory:")
    t = _tool(mem=mem, esc=esc)
    _set(t, "u2", user_input="多少錢")
    out = asyncio.run(t.execute(reason="報價"))
    assert "尚未掌握" in out
    recs = esc.list_for_user("locksmart", "u2")
    assert recs[0].is_explicit is True   # 「多少錢」是金錢字眼


def test_escalation_store_scope_enforced():
    esc = EscalationStore(":memory:")
    try:
        esc.log("", "u1", "r", False, {})
        assert False, "缺 tenant 應拋錯"
    except ValueError:
        pass
    try:
        esc.list_for_user("locksmart", "")
        assert False, "缺 user_id 應拋錯"
    except ValueError:
        pass


def test_escalation_isolated_per_user():
    esc = EscalationStore(":memory:")
    esc.log("locksmart", "a", "ra", False, {})
    esc.log("locksmart", "b", "rb", True, {})
    a = esc.list_for_user("locksmart", "a")
    assert len(a) == 1 and a[0].reason == "ra"
    # 跨 tenant 不互通
    assert esc.list_for_user("other", "a") == []
