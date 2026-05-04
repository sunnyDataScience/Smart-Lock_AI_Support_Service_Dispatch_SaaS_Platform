"""ReAct agent — 極簡版智慧鎖 AI 客服（product_info 架構）。

使用 langgraph.prebuilt.create_react_agent，搭配 load_product_info /
update_user_info / transfer_to_human 三個 tool，讓 LLM 依用戶 profile 載入
對應的產品資料（mega-doc）後回答客戶問題。

所有設定從 config.toml 讀取，所有提示詞從 prompts/*.md 讀取。
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from core.config import AppConfig, load_prompt
from agent_tools.tools import load_product_info, update_user_info, transfer_to_human, set_profile_mgr, set_transfer_message_from_file
from product_info import load_all_docs as load_product_docs


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
    # 1. 載入產品資訊（mega-doc 架構）
    from pathlib import Path
    product_info_dir = Path(__file__).parent / "product_info"
    product_docs = load_product_docs(product_info_dir)
    print(f"[agent] 載入 {len(product_docs)} 份產品資訊文件")

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
    agent = create_react_agent(
        model=model,
        tools=[load_product_info, update_user_info, transfer_to_human],
        prompt=prompt,
        checkpointer=checkpointer,
        name=cfg.system.get("agent_name", "smart_lock_agent"),
    )

    return agent
