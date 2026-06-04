"""驗證 Dream(nanobot 記憶整理)已拔掉自動建 skill 的能力(多用戶客服紅線)。

關鍵保證:Dream 的工具註冊表沒有 write_file → 物理上無法產生 skills/<name>/SKILL.md;
read_file / edit_file 仍在,供記憶整理(編輯 MEMORY.md / USER.md)。
"""

from lockcore.agent.memory import Dream, MemoryStore
from lockcore.providers.litellm_provider import LiteLLMProvider


def _make_dream(tmp_path):
    store = MemoryStore(workspace=tmp_path)
    provider = LiteLLMProvider(default_model="claude-sonnet-4-5")
    return Dream(store=store, provider=provider, model="claude-sonnet-4-5")


def test_dream_has_no_write_file_tool(tmp_path):
    dream = _make_dream(tmp_path)
    names = dream._tools.tool_names
    assert "write_file" not in names, "Dream 不應能寫檔(否則可自動建 skill)"


def test_dream_keeps_memory_editing_tools(tmp_path):
    dream = _make_dream(tmp_path)
    names = dream._tools.tool_names
    assert "read_file" in names
    assert "edit_file" in names
