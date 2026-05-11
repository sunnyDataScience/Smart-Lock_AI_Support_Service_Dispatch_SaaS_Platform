"""Skill-based ReAct agent — 極簡版智慧鎖 AI 客服。

使用 langgraph.prebuilt.create_react_agent，搭配 load_skill tool，
讓 LLM 自行判斷何時載入技能 SOP 來回答客戶問題。

所有設定從 config.toml 讀取，所有提示詞從 prompts/*.md 讀取。
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from core.config import AppConfig, load_prompt
from skills import load_skills
from skills.tools import (
    load_skill,
    load_product_info,
    update_user_info,
    transfer_to_human,
    set_skills,
    set_profile_mgr,
    set_transfer_message_from_file,
)


_system_prompt: str = ""


def get_system_prompt() -> str:
    """回傳目前使用中的 system prompt（供 debug 印出）。"""
    return _system_prompt


def build_agent(model, cfg: AppConfig, checkpointer=None, profile_mgr=None):
    """建立 skill-based ReAct agent。

    Args:
        model: LangChain ChatModel instance
        cfg: AppConfig from config.toml
        checkpointer: LangGraph checkpointer instance（由 memory.get_checkpointer 建立）
        profile_mgr: ProfileManager instance（用於 transfer_to_human 自動帶入資料）

    Returns:
        compiled LangGraph agent
    """
    # 1. 載入技能
    skills_dir = cfg.skills.get("data_dir")
    skills = load_skills(skills_dir)
    set_skills(skills)

    # 2. 注入 ProfileManager（轉接真人表單自動帶入）
    if profile_mgr:
        set_profile_mgr(profile_mgr)

    # 3. 組裝 system prompt（技能清單改為動態注入，不再靜態寫入）
    global _system_prompt
    prompt = load_prompt(
        cfg.prompts.get("system_prompt", "prompts/system.md"),
    )
    _system_prompt = prompt

    # 4. 載入轉接真人訊息模板（fallback，新版 transfer_to_human 已自動組裝）
    transfer_prompt_path = cfg.prompts.get("transfer_human_form", "prompts/transfer_human.md")
    set_transfer_message_from_file(transfer_prompt_path)

    # 4. 建立 agent
    # load_skill + load_product_info 並存（A 退場過渡）：
    # - load_product_info 是新主路（product_info DB）
    # - load_skill 暫保留向後兼容直到 system.md / skills_prefix / quality_check
    #   全部對齊新 catalog；後續 commit 會 drop
    agent = create_react_agent(
        model=model,
        tools=[load_skill, load_product_info, update_user_info, transfer_to_human],
        prompt=prompt,
        checkpointer=checkpointer,
        name=cfg.system.get("agent_name", "smart_lock_agent"),
    )

    return agent
