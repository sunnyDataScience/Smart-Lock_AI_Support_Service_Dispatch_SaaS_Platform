"""per-user 記憶層測試 — 重點:跨 user/tenant 隔離、default deny、CJK 檢索。"""

import pytest

from lockcore.agent.user_memory import MemoryManager, MemoryStore, SqliteMemoryProvider


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore(":memory:")
    yield s
    s.close()


# ---- 隔離(核心)----
def test_cross_user_isolation(store: MemoryStore):
    store.add("locksmart", "userA", "fact", "客人 A 使用 Dormakaba AS701")
    store.add("locksmart", "userB", "fact", "客人 B 使用 Chatlock AI-99")

    a = store.list_for_user("locksmart", "userA")
    b = store.list_for_user("locksmart", "userB")
    assert len(a) == 1 and "AS701" in a[0].content
    assert len(b) == 1 and "AI-99" in b[0].content
    # A 的內容不會出現在 B 的查詢
    assert all("AS701" not in e.content for e in b)
    # 搜尋也隔離:用 A 的關鍵字查 B → 空
    assert store.search("locksmart", "userB", "AS701") == []


def test_cross_tenant_isolation(store: MemoryStore):
    store.add("locksmart", "u1", "fact", "鎖市的客人")
    store.add("otherShop", "u1", "fact", "別家店的客人")  # 同 user_id 不同 tenant
    rows = store.list_for_user("locksmart", "u1")
    assert len(rows) == 1
    assert "鎖市" in rows[0].content


# ---- default deny ----
def test_default_deny_on_missing_scope(store: MemoryStore):
    with pytest.raises(ValueError):
        store.add("", "u1", "fact", "x")
    with pytest.raises(ValueError):
        store.add("locksmart", "", "fact", "x")
    with pytest.raises(ValueError):
        store.search("locksmart", "", "x")
    with pytest.raises(ValueError):
        store.list_for_user("", "u1")


def test_invalid_kind_rejected(store: MemoryStore):
    with pytest.raises(ValueError):
        store.add("locksmart", "u1", "bogus", "x")


def test_empty_content_rejected(store: MemoryStore):
    with pytest.raises(ValueError):
        store.add("locksmart", "u1", "fact", "   ")


# ---- 檢索(含 CJK 子字串)----
def test_search_roundtrip_cjk(store: MemoryStore):
    store.add("locksmart", "u1", "fact", "客人家裡裝的是 Dormakaba AS701 電子鎖")
    assert len(store.search("locksmart", "u1", "AS701")) == 1
    assert len(store.search("locksmart", "u1", "電子鎖")) == 1  # trigram CJK 子字串
    assert store.search("locksmart", "u1", "Milre") == []


def test_kind_filter(store: MemoryStore):
    store.add("locksmart", "u1", "preference", "偏好用密碼開門")
    store.add("locksmart", "u1", "issue", "門關不上")
    only_pref = store.list_for_user("locksmart", "u1", kinds=["preference"])
    assert len(only_pref) == 1 and only_pref[0].kind == "preference"


def test_forget_only_target_user(store: MemoryStore):
    store.add("locksmart", "u1", "fact", "a")
    store.add("locksmart", "u2", "fact", "b")
    removed = store.forget("locksmart", "u1")
    assert removed == 1
    assert store.list_for_user("locksmart", "u1") == []
    assert len(store.list_for_user("locksmart", "u2")) == 1


# ---- MemoryManager(BUILD/SAVE 掛點)----
def test_manager_record_then_prefetch():
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    # SAVE:寫回本輪
    n = mgr.record_turn("locksmart", "u1", "我的鎖是 Dormakaba AS701", session_id="s1")
    assert n == 1
    # BUILD:該客人之後再問,prefetch 召回
    block = mgr.build_context_block("locksmart", "u1", "AS701")
    assert "<memory>" in block and "AS701" in block
    # 不同客人 → 空區塊
    assert mgr.build_context_block("locksmart", "u2", "AS701") == ""


def test_manager_empty_block_when_no_memory():
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    assert mgr.build_context_block("locksmart", "new-user", "任何問題") == ""
