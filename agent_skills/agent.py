"""Skill-based ReAct agent — 極簡版智慧鎖 AI 客服。

使用 langgraph.prebuilt.create_react_agent，搭配 load_skill tool，
讓 LLM 自行判斷何時載入技能 SOP 來回答客戶問題。

所有設定從 config.toml 讀取，所有提示詞從 prompts/*.md 讀取。
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from core.config import AppConfig, load_prompt
from skills import load_skills
from skills.tools import load_skill, transfer_to_human, set_skills, set_transfer_message_from_file, build_skills_prompt


def build_agent(model, cfg: AppConfig):
    """建立 skill-based ReAct agent。

    Args:
        model: LangChain ChatModel instance
        cfg: AppConfig from config.toml

    Returns:
        compiled LangGraph agent
    """
    # 1. 載入技能
    skills_dir = cfg.skills.get("data_dir")
    skills = load_skills(skills_dir)
    set_skills(skills)

    # 2. 組裝 system prompt（從 prompts/system.md 模板 + config 變數）
    skills_section = build_skills_prompt(skills)

    prompt = load_prompt(
        cfg.prompts.get("system_prompt", "prompts/system.md"),
        skills_section=skills_section,
    )

    # 3. 載入轉接真人訊息模板
    transfer_prompt_path = cfg.prompts.get("transfer_human_form", "prompts/transfer_human.md")
    set_transfer_message_from_file(transfer_prompt_path)

    # 4. 建立 agent
    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=model,
        tools=[load_skill, transfer_to_human],
        prompt=prompt,
        checkpointer=checkpointer,
        name=cfg.system.get("agent_name", "smart_lock_agent"),
    )

    return agent
