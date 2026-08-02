"""workspace-global history 不得跨客人洩漏（CR-0200，2026-08-02）。

**原問題**：`line_gateway.py` 為**整個 process** 建立一個 workspace，而
`ContextBuilder.build_system_prompt` 會把該 workspace 的 `memory/history.jsonl`
無條件注入成「# Recent History」。

`read_unprocessed_history(since_cursor)` **只用 cursor 過濾，沒有任何使用者維度**
（`memory.py:318-320`），所以 A 客人被 consolidation 歸檔的對話——含姓名、地址、
電話——會出現在 B 客人的 system prompt 裡。而 dream cursor 在 gateway 從不前進
（`/dream` 指令未被排程），那筆內容會**永久**留在注入範圍內。

**修法**：`ContextBuilder` / `AgentLoop` 加向後相容的 `inject_workspace_history`
（預設 True＝上游行為不變），LINE gateway 傳 False。

關掉不損失任何東西：本專案的 per-user 記憶走 `memory_manager`
（`lockcore/agent/user_memory/`，有 tenant+user_id 隔離），
workspace-global history 是上游單機私人助理情境的殘留。

## 這個檔案怎麼測

**不是**斷言「有沒有傳這個旗標」——那種測試在本輪已經失手過一次
（沙箱修正的第一版是 no-op，但只看設定欄位的測試會是綠的）。
這裡直接**寫一筆 A 客人的內容進 history，然後檢查 B 客人的 system prompt 裡有沒有**。
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from lockcore.agent.context import ContextBuilder

# 模擬 A 客人被歸檔的對話——用實際會外洩的東西（姓名 + 電話 + 地址）
_LEAK = "客戶王小明 0912345678 台北市信義路100號 反映指紋辨識失靈"


@pytest.fixture
def workspace_with_history():
    ws = pathlib.Path(tempfile.mkdtemp(prefix="hist-iso-"))
    cb = ContextBuilder(ws)          # 預設 True，用來寫入
    cb.memory.append_history(_LEAK)
    return ws


def test_history_leaks_across_users_when_injection_is_on(workspace_with_history):
    """釘住漏洞本身——證明這個測試真的抓得到，不是恆真。

    上游預設（True）下，A 客人的內容確實會進到任何人的 system prompt。
    """
    cb = ContextBuilder(workspace_with_history, inject_workspace_history=True)
    prompt = cb.build_system_prompt()
    assert _LEAK in prompt, (
        "上游預設下沒有注入 history——本測試的前提已改變，請重新確認 CR-0200 是否仍成立"
    )


def test_history_is_not_injected_when_disabled(workspace_with_history):
    """核心：關掉之後，A 客人的內容不可出現在 system prompt。"""
    cb = ContextBuilder(workspace_with_history, inject_workspace_history=False)
    prompt = cb.build_system_prompt()

    assert _LEAK not in prompt, "關掉注入後仍看得到其他客人的對話內容"
    assert "# Recent History" not in prompt, "Recent History 區塊仍被注入"


def test_disabling_history_keeps_the_rest_of_the_prompt(workspace_with_history):
    """關掉 history 不可把別的東西一起關掉——prompt 仍要有實質內容。"""
    on = ContextBuilder(workspace_with_history, inject_workspace_history=True).build_system_prompt()
    off = ContextBuilder(workspace_with_history, inject_workspace_history=False).build_system_prompt()

    assert len(off) > 200, f"關掉後 prompt 只剩 {len(off)} 字元，可能誤刪了其他區塊"
    # 差異應該只有 history 那一段
    assert len(on) > len(off), "關掉後長度沒變短——注入可能根本沒生效"


def test_default_is_upstream_behaviour(workspace_with_history):
    """不傳參數時必須與上游一致（向後相容，符合 VENDOR.md 的本地改動慣例）。"""
    default = ContextBuilder(workspace_with_history).build_system_prompt()
    explicit_on = ContextBuilder(
        workspace_with_history, inject_workspace_history=True
    ).build_system_prompt()
    assert default == explicit_on


def test_line_gateway_disables_it():
    """接線層：LINE gateway 是多使用者通道，必須關掉。"""
    import ast

    gw = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "line_gateway.py"
    tree = ast.parse(gw.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
            if name == "AgentLoop":
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                assert "inject_workspace_history" in kw, (
                    "line_gateway 沒關掉 workspace-global history——"
                    "一個 workspace 服務所有客人，會跨客人洩漏 PII"
                )
                v = kw["inject_workspace_history"]
                assert isinstance(v, ast.Constant) and v.value is False, (
                    f"inject_workspace_history 必須是 False，實際是 {ast.dump(v)}"
                )
                return
    raise AssertionError("line_gateway.py 裡找不到 AgentLoop(...) 的建構呼叫")
