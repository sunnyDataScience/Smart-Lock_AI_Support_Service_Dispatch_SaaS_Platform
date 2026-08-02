"""檔案類工具的 workspace 沙箱（2026-08-02 資安掃描）。

**原問題**：`CS_TOOL_ALLOWLIST` 開了 `read_file / list_dir / find_files / grep`，
而 `restrict_to_workspace` 在 `lockcore/config/schema.py` 預設 **False**、
`agent/config.toml` 沒設、`line_gateway.py` 也沒傳——這個**面向 LINE 使用者**的
客服 agent 可以讀取整個檔案系統。

任何加官方帳號好友的陌生人都能用 prompt injection 誘導它讀 `/proc/self/environ`，
一次帶走 `scripts/deploy/agent.sh` 注入的全部機密：`LINE_CHANNEL_ACCESS_TOKEN`
（冒名推播全體好友）、`POSTGRES_URI`（直連 Cloud SQL）、`INTERNAL_API_TOKEN`
（呼叫 `/api/v1/internal/*`）。`reply_guard` 只驗金額與型號，對 token/URI 一律放行。

## 這個檔案為什麼直接斷言工具狀態，而不是斷言設定欄位

本次修正的**第一版是 no-op**：傳了 `AgentLoop(restrict_to_workspace=True)`，
看起來合理，實際上完全沒生效——那個 kwarg 只轉給 `SubagentManager`
（loop.py:256 → 288），而檔案工具讀的是 `ToolContext(config=self.tools_config)`
（loop.py:484），中間沒有任何一行同步。當時若只斷言「有傳這個參數」，測試會是綠的，
漏洞卻原封不動。是對抗驗證實跑 `read_file('/etc/hosts')` 才抓出來。

所以本檔的核心測試**直接建出工具、檢查 `_allowed_dir`、真的去讀 workspace 外的檔案**。
設定怎麼傳是實作細節，工具擋不擋得住才是要守的東西。
"""

from __future__ import annotations

import ast
import pathlib
import tempfile

import pytest

from lockcore.agent.tools.context import ToolContext
from lockcore.agent.tools.filesystem import ReadFileTool
from lockcore.config.schema import ToolsConfig

GATEWAY = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "line_gateway.py"


def _make_tool(tools_config: ToolsConfig, workspace: pathlib.Path) -> ReadFileTool:
    return ReadFileTool.create(
        ToolContext(
            config=tools_config,
            workspace=str(workspace),
            bus=None,
            subagent_manager=None,
            cron_service=None,
            file_state_store=None,
        )
    )


@pytest.fixture
def workspace(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "inside.txt").write_text("workspace 內的檔案\n", encoding="utf-8")
    return tmp_path


# =============================================================================
# 行為層：工具真的擋得住嗎（這才是要守的東西）
# =============================================================================


@pytest.mark.asyncio
async def test_sandboxed_tool_blocks_reads_outside_workspace(workspace):
    """核心：沙箱開啟時，workspace 外的檔案必須讀不到。"""
    tool = _make_tool(ToolsConfig(restrict_to_workspace=True), workspace)
    assert tool._allowed_dir is not None, "沙箱沒生效——_allowed_dir 仍是 None"

    result = await tool.execute(path="/etc/hosts")
    assert "outside" in str(result).lower() or "error" in str(result).lower(), (
        f"workspace 外的檔案竟然讀得到：{str(result)[:120]}"
    )


@pytest.mark.asyncio
async def test_sandboxed_tool_still_reads_builtin_skills(workspace):
    """沙箱不可把知識庫關在外面。

    上游在 filesystem.py 內建 `extra_read = [BUILTIN_SKILLS_DIR]`，
    開啟沙箱時自動把 lockcore/skills/ 列入可讀白名單。這條釘住那個行為——
    若上游哪天拿掉，產品知識查詢會整個失效而沒人知道。
    """
    from lockcore.agent.skills import BUILTIN_SKILLS_DIR

    skill_md = pathlib.Path(BUILTIN_SKILLS_DIR) / "locksmith-product-knowledge" / "SKILL.md"
    if not skill_md.is_file():
        pytest.skip(f"builtin skill 不存在：{skill_md}")

    tool = _make_tool(ToolsConfig(restrict_to_workspace=True), workspace)
    result = str(await tool.execute(path=str(skill_md)))
    assert "outside" not in result.lower(), "沙箱把 builtin skills 擋掉了——產品知識會查不到"


@pytest.mark.asyncio
async def test_sandboxed_tool_still_reads_inside_workspace(workspace):
    tool = _make_tool(ToolsConfig(restrict_to_workspace=True), workspace)
    result = str(await tool.execute(path=str(workspace / "inside.txt")))
    assert "outside" not in result.lower(), "workspace 內的檔案被誤擋"


@pytest.mark.asyncio
async def test_unsandboxed_tool_would_read_anything(workspace):
    """釘住「為什麼一定要設」——預設狀態確實讀得到 /etc/hosts。

    若上游哪天把預設改成安全的，這條會紅。那是好消息，屆時可簡化 line_gateway。
    """
    tool = _make_tool(ToolsConfig(), workspace)
    assert tool._allowed_dir is None
    result = str(await tool.execute(path="/etc/hosts"))
    assert "outside" not in result.lower(), (
        "上游預設已改為安全——請重新評估 line_gateway 的顯式設定是否仍必要"
    )


# =============================================================================
# 接線層：gateway 用的是會生效的那條路徑
# =============================================================================


def _agentloop_kwargs() -> dict[str, ast.expr]:
    tree = ast.parse(GATEWAY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
            if name == "AgentLoop":
                return {k.arg: k.value for k in node.keywords if k.arg}
    raise AssertionError("line_gateway.py 裡找不到 AgentLoop(...) 的建構呼叫")


def test_gateway_passes_tools_config_not_the_noop_kwarg():
    """gateway 必須用 tools_config；用 restrict_to_workspace kwarg 是 no-op。"""
    kwargs = _agentloop_kwargs()

    assert "restrict_to_workspace" not in kwargs, (
        "line_gateway 傳了 AgentLoop(restrict_to_workspace=...) —— **那是 no-op**。"
        "該 kwarg 只轉給 SubagentManager，檔案工具讀的是 tools_config。"
        "請改用 tools_config=ToolsConfig(restrict_to_workspace=True)。"
    )
    assert "tools_config" in kwargs, "line_gateway 沒傳 tools_config——沙箱不會生效"

    src = ast.unparse(kwargs["tools_config"])
    assert "restrict_to_workspace=True" in src.replace(" ", ""), (
        f"tools_config 沒開沙箱：{src}"
    )


def test_file_tools_are_in_the_allowlist():
    """釘住前提：沙箱之所以必要，是因為這些工具真的開著。"""
    from lockcore.app_config import CS_TOOL_ALLOWLIST

    for tool in ("read_file", "list_dir", "find_files", "grep"):
        assert tool in CS_TOOL_ALLOWLIST, f"{tool} 不在白名單——本測試的前提已改變"
