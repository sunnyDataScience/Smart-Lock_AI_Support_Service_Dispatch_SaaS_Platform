"""整合測試:透過真實 forked ContextBuilder 驗證 per-user 記憶在 BUILD 注入 + 隔離。

證明 fork 的價值:ContextBuilder 現在可注入我們的 MemoryManager(DI),
這是「當依賴」做不到的。也驗證未帶 user_id 時行為與上游一致(向後相容)。
"""

import pytest

from lockcore.agent.user_memory import MemoryManager, SqliteMemoryProvider
from lockcore.agent.context import ContextBuilder


@pytest.fixture
def ctx(tmp_path):
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    cb = ContextBuilder(workspace=tmp_path, memory_manager=mgr, tenant="locksmart")
    return cb, mgr


def test_build_injects_per_user_memory(ctx):
    cb, mgr = ctx
    # SAVE 側:記下 userA 本輪
    mgr.record_turn("locksmart", "userA", "我家的鎖是 Dormakaba AS701", session_id="s1")
    # BUILD 側:userA 之後再問 → 系統提示注入該客人記憶
    prompt_a = cb.build_system_prompt(user_id="userA", memory_query="AS701")
    assert "Customer Memory" in prompt_a
    assert "AS701" in prompt_a


def test_cross_user_isolation_in_prompt(ctx):
    cb, mgr = ctx
    mgr.record_turn("locksmart", "userA", "我家的鎖是 Dormakaba AS701")
    # userB 的系統提示不應出現 userA 的記憶
    prompt_b = cb.build_system_prompt(user_id="userB", memory_query="AS701")
    assert "AS701" not in prompt_b


def test_no_user_id_preserves_upstream_behavior(ctx):
    cb, mgr = ctx
    mgr.record_turn("locksmart", "userA", "我家的鎖是 Dormakaba AS701")
    # 沒帶 user_id → 不注入 Customer Memory(與上游 nanobot 行為一致)
    prompt = cb.build_system_prompt()
    assert "Customer Memory" not in prompt


def test_no_memory_manager_is_plain_upstream(tmp_path):
    # 未注入 memory_manager → 即使帶 user_id 也不注入(純上游行為)
    cb = ContextBuilder(workspace=tmp_path)
    prompt = cb.build_system_prompt(user_id="userA", memory_query="x")
    assert "Customer Memory" not in prompt


def test_build_messages_threads_user_id(ctx):
    """loop 實際呼叫的是 build_messages(帶 sender_id);驗證它把 user_id 串到 BUILD。"""
    cb, mgr = ctx
    mgr.record_turn("locksmart", "userA", "我家的鎖是 Dormakaba AS701")
    # sender_id=userA → 系統訊息含該客人記憶
    msgs_a = cb.build_messages(history=[], current_message="AS701 怎麼改密碼", sender_id="userA")
    sys_a = msgs_a[0]["content"]
    assert "Customer Memory" in sys_a and "AS701" in sys_a
    # sender_id=userB → 不含(隔離)
    msgs_b = cb.build_messages(history=[], current_message="AS701 怎麼改密碼", sender_id="userB")
    assert "AS701" not in msgs_b[0]["content"]
