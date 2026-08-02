"""檔案類工具的 workspace 沙箱（2026-08-02 資安掃描）。

**原問題**：`CS_TOOL_ALLOWLIST` 開了 `read_file / list_dir / find_files / grep`，
而 `restrict_to_workspace` 在 `lockcore/config/schema.py` 的預設是 **False**，
`agent/config.toml` 也沒設定它，`line_gateway.py` 建 `AgentLoop` 時同樣沒傳——
三者疊加＝這個**面向 LINE 使用者**的客服 agent 可以讀取整個檔案系統。

實際攻擊面：使用者用 prompt injection 誘導 AI 讀 `.env`
（`GEMINI_API_KEY` / `LINE_CHANNEL_ACCESS_TOKEN`）或 `credentials.json`
並把內容回覆出來。門檻只是「會打字」，比需要知道 UUID 的漏洞低得多。

**修法**：`line_gateway.py` 傳 `restrict_to_workspace=True`，
並在啟動時把 builtin skills 複製進 workspace。

## 為什麼兩件事必須綁在一起

只開沙箱而不鋪 builtin skills，`SkillSync` 首輪完成前（或品牌庫連不上時）
`workspace/skills/` 是空的，agent 讀不到 `references/`，產品知識查詢直接失效。
builtin 的定位本來就是「出廠範本＋離線保底」，保底不能因為加了沙箱就消失。

所以本檔的兩組測試是一體的：**沙箱開著** ＋ **保底還在**。
少任何一邊，這個修正就是壞的。
"""

from __future__ import annotations

import ast
import pathlib
import shutil
import tempfile

import pytest

GATEWAY = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "line_gateway.py"


def _agentloop_kwargs() -> dict[str, ast.expr]:
    """從原始碼取出 line_gateway 建 AgentLoop 時傳的 keyword 參數。

    用 AST 而非執行：`main()` 會真的起 web server 並要求 LINE 憑證，
    測試不該有那些副作用。AST 讀的是「原始碼寫了什麼」，正是要釘住的東西。
    """
    tree = ast.parse(GATEWAY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
            if name == "AgentLoop":
                return {k.arg: k.value for k in node.keywords if k.arg}
    raise AssertionError("line_gateway.py 裡找不到 AgentLoop(...) 的建構呼叫")


# =============================================================================
# 沙箱必須是開的
# =============================================================================


def test_agent_loop_restricts_tools_to_workspace():
    """這是本檔的核心：拿掉 restrict_to_workspace=True 就會紅。"""
    kwargs = _agentloop_kwargs()
    assert "restrict_to_workspace" in kwargs, (
        "line_gateway 沒有傳 restrict_to_workspace——"
        "lockcore 的預設是 False，等於檔案工具可讀整個檔案系統"
    )
    node = kwargs["restrict_to_workspace"]
    assert isinstance(node, ast.Constant) and node.value is True, (
        f"restrict_to_workspace 必須是 True，實際是 {ast.dump(node)}"
    )


def test_lockcore_default_is_still_unsafe_so_we_must_pass_it_explicitly():
    """釘住「為什麼一定要顯式傳」——上游預設是 False。

    若日後上游把預設改成 True，這條會紅，屆時可以簡化 line_gateway。
    它紅掉是好消息，不是壞消息。
    """
    from lockcore.config.schema import ToolsConfig

    assert ToolsConfig().restrict_to_workspace is False, (
        "上游預設已改變——請重新評估 line_gateway 的顯式設定是否仍必要"
    )


def test_file_tools_are_in_the_allowlist():
    """釘住前提：沙箱之所以必要，是因為這些工具真的開著。"""
    from lockcore.app_config import CS_TOOL_ALLOWLIST

    for tool in ("read_file", "list_dir", "find_files", "grep"):
        assert tool in CS_TOOL_ALLOWLIST, f"{tool} 不在白名單——本測試的前提已改變"


# =============================================================================
# 保底必須還在（沙箱不能把知識庫關在外面）
# =============================================================================


def test_seed_copies_builtin_skills_with_references():
    """builtin skills 與其 references 必須真的被複製進 workspace。"""
    from scripts.line_gateway import _seed_builtin_skills

    ws = pathlib.Path(tempfile.mkdtemp(prefix="sandbox-test-"))
    try:
        _seed_builtin_skills(ws)
        dest = ws / "skills"
        assert dest.is_dir(), "workspace/skills 沒被建立"

        names = {d.name for d in dest.iterdir() if d.is_dir()}
        assert "locksmith-product-knowledge" in names, f"產品知識 skill 沒進來：{names}"
        assert "locksmith-cs-sop" in names, f"客服 SOP skill 沒進來：{names}"

        refs = dest / "locksmith-product-knowledge" / "references"
        assert refs.is_dir(), "references/ 沒跟著複製——沙箱下產品知識會查不到"
        assert sum(1 for _ in refs.rglob("*.md")) > 0, "references/ 是空的"
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_seed_does_not_create_symlinks_that_escape_the_sandbox():
    """symlink 會被 resolve() 解回 workspace 外的真實路徑，沙箱判定當場失效。"""
    from scripts.line_gateway import _seed_builtin_skills

    ws = pathlib.Path(tempfile.mkdtemp(prefix="sandbox-test-"))
    try:
        _seed_builtin_skills(ws)
        escaped = [p for p in (ws / "skills").rglob("*") if p.is_symlink()]
        assert not escaped, f"複製後出現 symlink，沙箱可被繞過：{escaped}"
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_seed_is_fail_soft(monkeypatch, caplog):
    """複製失敗只記錄不中止——起不來的 agent 什麼都做不了，連轉真人都不行。"""
    from scripts import line_gateway as gw

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(gw.shutil, "copytree", boom)
    ws = pathlib.Path(tempfile.mkdtemp(prefix="sandbox-test-"))
    try:
        with caplog.at_level("ERROR"):
            gw._seed_builtin_skills(ws)   # 不可拋出
        assert any(r.levelname == "ERROR" for r in caplog.records), "失敗時沒有留下記錄"
    finally:
        shutil.rmtree(ws, ignore_errors=True)
