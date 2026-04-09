"""load_skill + transfer_to_human tools。"""

from __future__ import annotations

import os

from langchain_core.tools import tool

from . import Skill

# ── 模組層級狀態（由 app 啟動時注入）──
_skills: list[Skill] = []
_transfer_message: str = ""


def set_skills(skills: list[Skill]) -> None:
    """注入技能清單（app 啟動時呼叫）。"""
    global _skills
    _skills = skills


@tool
def load_skill(skill_name: str) -> str:
    """載入指定技能的完整 SOP 內容到對話中。

    當你需要某個技能的詳細步驟、追問話術、品牌對照表等完整資訊時，
    使用此工具載入。

    Args:
        skill_name: 技能名稱，例如 "troubleshoot"、"ts-door-stuck"、"app-guide"
    """
    for s in _skills:
        if s.name == skill_name:
            print(f"[skill] >>> 載入技能: {s.name}")
            return f"已載入技能: {s.name}\n\n{s.content}"

    available = ", ".join(s.name for s in _skills)
    print(f"[skill] >>> 找不到: {skill_name}")
    return f"找不到技能 '{skill_name}'。可用技能: {available}"


@tool
def transfer_to_human(reason: str) -> str:
    """轉接真人客服。當客戶明確要求轉真人、或問題超出 AI 能力範圍時使用。

    觸發情境：客戶說「轉真人」「我要找真人」「找專員」「找人工客服」「幫我轉接」
    「我不要跟機器人講」「讓我跟人說話」等任何表達想與真人對話的意圖。

    Args:
        reason: 轉接原因摘要
    """
    print(f"[transfer] >>> 轉接真人: {reason}")
    # TODO: 實際串接 LINE 轉接或通知機制
    return _transfer_message


def set_transfer_message_from_file(prompt_path: str) -> None:
    """從提示詞檔案載入轉接真人訊息（agent.py 啟動時呼叫）。"""
    global _transfer_message
    _transfer_message = _load_prompt_file(prompt_path)


def _load_prompt_file(prompt_path: str) -> str:
    """讀取提示詞檔案（相對於 agent_skills/）。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_skills_prompt(skills: list[Skill]) -> str:
    """產生注入 system prompt 的技能摘要清單。"""
    lines = ["## 可用技能\n"]
    for s in skills:
        lines.append(f"- **{s.name}**: {s.description}")
    lines.append(
        "\n當客戶的問題符合某個技能時，請使用 `load_skill` 工具載入該技能的完整 SOP，"
        "然後依照 SOP 步驟引導客戶。"
    )
    return "\n".join(lines)
