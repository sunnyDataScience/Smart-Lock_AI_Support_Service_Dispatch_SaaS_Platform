"""客服工具裁剪(tool_allowlist)測試 — 不打 API。"""

import tempfile
from pathlib import Path
from typing import Any

from lockcore.agent.loop import AgentLoop
from lockcore.app_config import CS_TOOL_ALLOWLIST
from lockcore.bus.queue import MessageBus
from lockcore.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    def get_default_model(self) -> str:
        return "mock-model"

    async def chat(self, messages: list[dict[str, Any]], tools=None, model=None,
                   max_tokens: int = 4096, temperature: float = 0.7,
                   reasoning_effort=None, tool_choice=None) -> LLMResponse:
        return LLMResponse(content="ok", finish_reason="stop")


def _loop(allowlist):
    return AgentLoop(
        bus=MessageBus(),
        provider=_MockProvider(),
        workspace=Path(tempfile.mkdtemp(prefix="lockcore-test-")),
        model="mock-model",
        tool_allowlist=allowlist,
    )


def test_allowlist_keeps_only_listed():
    loop = _loop(CS_TOOL_ALLOWLIST)
    names = set(loop.tools.tool_names)
    # 命脈 + 兜底 + 轉真人 保留
    assert "read_file" in names
    assert "web_search" in names
    assert "transfer_to_human" in names
    # 危險 / 無用工具被砍
    for danger in ("write_file", "edit_file", "exec", "spawn", "cron", "message", "web_fetch"):
        assert danger not in names, f"{danger} 應被裁掉"
    # 不會多出白名單以外的東西
    assert names <= CS_TOOL_ALLOWLIST


def test_no_allowlist_keeps_default_set():
    loop = _loop(None)
    names = set(loop.tools.tool_names)
    # 不裁時上游工具還在(回歸:確認裁剪是 opt-in)
    assert "write_file" in names
    assert "read_file" in names


def test_product_knowledge_read_tools_survive():
    """讀 skill 知識的命脈工具(read_file/list_dir/find_files/grep)務必都在。"""
    loop = _loop(CS_TOOL_ALLOWLIST)
    names = set(loop.tools.tool_names)
    for t in ("read_file", "list_dir", "find_files", "grep"):
        assert t in names, f"{t} 是讀產品知識的命脈,不可被裁"
