"""MCP 工具與 CS_TOOL_ALLOWLIST 的邊界（2026-07-27 稽核補正）。

**這支測試釘住的是一個「刻意設計」而非缺陷**，但它此前完全沒有測試守著，且
CLAUDE.md 的 Architecture Lock 第 4 條原本寫成「工具白名單只能在 CS_TOOL_ALLOWLIST
統一控」，讀起來像是**所有**工具都受該白名單約束 —— 實際不然。

行為根源是**時序**：
  1. `AgentLoop.__init__` 同步註冊內建工具後，依 `tool_allowlist` 一次性 unregister
     不在名單內者（`loop.py` 的 `_register_default_tools()` → allowlist strip）。
  2. MCP 連線發生在**事件迴圈啟動之後**（`line_gateway.py` on_startup →
     `loop._connect_mcp()`），`tools/mcp.py` 只做 `registry.register(wrapper)`，
     全檔沒有任何 allowlist 檢查。

因此 MCP 工具是**第二條工具入口**，不經白名單。控制點在 `agent/config.toml` 的
`[mcp_servers.*]` 與其 `${ENV}` 是否解得到值（解不到 → 整個 server 跳過）。

守線目的：若日後有人「順手」把 MCP 註冊移進建構期、或把 allowlist 改成事後套用，
本測試會紅，逼出一次明確的決策（而不是靜默改變 LLM 可見的工具面）。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lockcore.agent.loop import AgentLoop
from lockcore.agent.tools.base import Tool
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


class _FakeMcpTool(Tool):
    """模擬 MCP wrapper 註冊進來的工具（命名沿用實際的 mcp_<server>_<tool> 形狀）。"""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "fake mcp tool for boundary test"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover - 不會被呼叫
        return "noop"


def _loop() -> AgentLoop:
    return AgentLoop(
        bus=MessageBus(),
        provider=_MockProvider(),
        workspace=Path(tempfile.mkdtemp(prefix="lockcore-mcp-bound-")),
        model="mock-model",
        tool_allowlist=CS_TOOL_ALLOWLIST,
    )


def test_builtin_tools_are_confined_to_allowlist():
    """建構完成當下，內建工具必須是白名單的子集（第 4 條的前半段成立）。"""
    loop = _loop()
    names = set(loop.tools.tool_names)
    assert names <= set(CS_TOOL_ALLOWLIST), (
        f"建構期有工具逸出白名單：{sorted(names - set(CS_TOOL_ALLOWLIST))}"
    )
    assert "transfer_to_human" in names, "唯一進線工具不得被裁掉"


def test_mcp_tools_bypass_allowlist_by_design():
    """MCP 工具在建構之後註冊 → **不受**白名單約束（刻意設計，非缺陷）。

    若本測試轉紅，代表註冊時序或 allowlist 套用方式被改動 —— 那是 architecture
    change，須走 CIA 並同步更新 CLAUDE.md 第 4 條的 MCP 例外說明。
    """
    loop = _loop()
    before = set(loop.tools.tool_names)

    # 模擬 _connect_mcp 之後的狀態（實際 wrapper 名稱形狀：mcp_<server>_<tool>）
    for name in ("mcp_locksmith-rag_search_product_manual",
                 "mcp_locksmith-rag_search_similar_cases"):
        loop.tools.register(_FakeMcpTool(name))

    after = set(loop.tools.tool_names)
    added = after - before

    assert len(added) == 2, f"MCP 工具未被註冊進 registry：{added}"
    assert not (after <= set(CS_TOOL_ALLOWLIST)), (
        "MCP 工具竟被白名單擋下 —— 與 ADR-010/CR-0125 的設計不符；"
        "若這是刻意改動，請走 CIA 並更新 CLAUDE.md 第 4 條"
    )
    assert added.isdisjoint(set(CS_TOOL_ALLOWLIST)), (
        "測試前提失效：模擬的 MCP 工具名不該出現在白名單內"
    )


def test_mcp_registration_happens_after_construction():
    """釘住時序本身：_connect_mcp 不在 __init__ 內被呼叫。

    這是「MCP 不受白名單約束」的**成因**。若有人把 _connect_mcp 移進建構期，
    MCP 工具就會被 allowlist strip 砍掉（RAG 靜默失效），本測試先攔下。
    """
    import inspect

    src = inspect.getsource(AgentLoop.__init__)
    assert "_connect_mcp" not in src, (
        "_connect_mcp 被移進 __init__ —— MCP 工具會被建構期的 allowlist strip 砍掉，"
        "導致 RAG 靜默失效"
    )
