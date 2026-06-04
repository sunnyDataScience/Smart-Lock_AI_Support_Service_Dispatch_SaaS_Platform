"""端到端(mock provider,不打 API):一則訊息跑完整 turn,驗證
進訊息 → BUILD 注入該客人記憶 + skill → (假)LLM 回覆 → SAVE 寫回記憶 → 跨 user 隔離。
"""

import asyncio
from typing import Any

import pytest

from lockcore.agent.loop import AgentLoop
from lockcore.agent.user_memory import MemoryManager, SqliteMemoryProvider
from lockcore.bus.events import InboundMessage
from lockcore.bus.queue import MessageBus
from lockcore.providers.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """回固定答案、擷取收到的 system prompt 供斷言。"""

    def __init__(self):
        super().__init__()
        self.last_system_prompt: str = ""

    def get_default_model(self) -> str:
        return "mock-model"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools=None,
        model=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort=None,
        tool_choice=None,
    ) -> LLMResponse:
        sys = next((m for m in messages if m.get("role") == "system"), None)
        self.last_system_prompt = (sys or {}).get("content", "") if sys else ""
        return LLMResponse(content="好的,已為您記下。", finish_reason="stop")


def _make_loop(tmp_path, mgr):
    return AgentLoop(
        bus=MessageBus(),
        provider=MockProvider(),
        workspace=tmp_path,
        model="mock-model",
        memory_manager=mgr,
        memory_tenant="locksmart",
    )


def _turn(loop, sender_id, content):
    msg = InboundMessage(channel="cli", sender_id=sender_id, chat_id=sender_id, content=content)
    return asyncio.run(loop._process_message(msg, session_key=f"locksmart:{sender_id}"))


def test_e2e_memory_roundtrip_and_isolation(tmp_path):
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    loop = _make_loop(tmp_path, mgr)
    prov = loop.provider

    # turn 1:userA 透露鎖型號 → SAVE 應寫回該客人記憶
    out1 = _turn(loop, "userA", "我家的鎖是 Dormakaba AS701")
    assert out1 is not None
    assert mgr.provider.store.list_for_user("locksmart", "userA"), "turn1 後應有 userA 記憶"

    # turn 2:userA 再問 → BUILD 應把該客人記憶注入 system prompt
    _turn(loop, "userA", "怎麼改密碼")
    assert "AS701" in prov.last_system_prompt

    # turn 3:userB → 不應看到 userA 的記憶(隔離)
    _turn(loop, "userB", "你好")
    assert "AS701" not in prov.last_system_prompt


def test_e2e_skill_in_system_prompt(tmp_path):
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    loop = _make_loop(tmp_path, mgr)
    prov = loop.provider
    _turn(loop, "userC", "你們有賣電子鎖嗎")
    # builtin skill 摘要應出現在 system prompt
    assert "locksmith-product-knowledge" in prov.last_system_prompt \
        or "locksmith-cs-sop" in prov.last_system_prompt
