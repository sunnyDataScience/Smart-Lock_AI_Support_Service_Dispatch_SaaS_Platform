"""LLM 記憶抽取器測試 — 用 mock provider,不打 API。"""

import asyncio
from typing import Any

from lockcore.agent.user_memory import LLMExtractor, MemoryManager, SqliteMemoryProvider
from lockcore.agent.user_memory.llm_extractor import _parse


class _StubProvider:
    """回固定 JSON 字串的假 provider。"""

    def __init__(self, content: str):
        self._content = content
        self.calls = 0

    async def chat(self, messages, model=None, max_tokens=512, temperature=0.0, **kw) -> Any:
        self.calls += 1

        class _R:
            content = self._content
            finish_reason = "stop"

        return _R()


def test_parse_plain_json():
    out = _parse('[{"kind":"fact","content":"客人的鎖是 Dormakaba AS701"}]')
    assert out == [("fact", "客人的鎖是 Dormakaba AS701")]


def test_parse_fenced_json():
    out = _parse('```json\n[{"kind":"profile","content":"電話 0912"}]\n```')
    assert out == [("profile", "電話 0912")]


def test_parse_rejects_bad_kind_and_empty():
    out = _parse('[{"kind":"random","content":"x"},{"kind":"fact","content":""},'
                 '{"kind":"fact","content":"有效"}]')
    assert out == [("fact", "有效")]


def test_parse_garbage_returns_empty():
    assert _parse("我不知道") == []
    assert _parse("") == []


def test_extractor_returns_clean_facts():
    prov = _StubProvider('[{"kind":"fact","content":"客人的鎖是 Dormakaba AS701"}]')
    ext = LLMExtractor(prov, "mock-model")
    out = asyncio.run(ext("我家 Dormakaba AS701 怎麼改密碼", "請按..."))
    assert out == [("fact", "客人的鎖是 Dormakaba AS701")]
    assert prov.calls == 1


def test_extractor_filters_noise_via_empty_array():
    prov = _StubProvider("[]")   # 模型判定閒聊 → 不抽
    ext = LLMExtractor(prov, "mock-model")
    out = asyncio.run(ext("附近有沒有火鍋店", "不好意思這超出..."))
    assert out == []


def test_extractor_empty_user_skips_call():
    prov = _StubProvider("[]")
    ext = LLMExtractor(prov, "mock-model")
    out = asyncio.run(ext("", "x"))
    assert out == []
    assert prov.calls == 0   # 空訊息不打 provider


def test_provider_async_path_with_llm_extractor():
    prov = _StubProvider('[{"kind":"fact","content":"客人的鎖是 Kaadas K9"}]')
    mp = SqliteMemoryProvider(":memory:", extractor=LLMExtractor(prov, "mock-model"))
    mgr = MemoryManager(mp)
    n = asyncio.run(mgr.record_turn_async("locksmart", "u1", "我的鎖 Kaadas K9", "好的"))
    assert n == 1
    entries = mp.store.list_for_user("locksmart", "u1")
    assert entries[0].content == "客人的鎖是 Kaadas K9"
    assert entries[0].kind == "fact"


def test_sync_turn_rejects_async_extractor():
    prov = _StubProvider("[]")
    mp = SqliteMemoryProvider(":memory:", extractor=LLMExtractor(prov, "mock-model"))
    try:
        mp.sync_turn("locksmart", "u1", "x", "y")
        assert False, "async extractor 走 sync_turn 應拋 TypeError"
    except TypeError:
        pass


def test_async_path_still_supports_sync_extractor():
    """sync 的 default_extractor 走 async 路徑也要正常(向後相容)。"""
    mp = SqliteMemoryProvider(":memory:")   # default_extractor(sync)
    n = asyncio.run(mp.sync_turn_async("locksmart", "u1", "整句會被存", "回覆"))
    assert n == 1
