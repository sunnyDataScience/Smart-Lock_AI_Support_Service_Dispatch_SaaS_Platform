"""Skill-based ReAct agent — 極簡版智慧鎖 AI 客服。

使用 langgraph.prebuilt.create_react_agent，搭配 load_skill tool，
讓 LLM 自行判斷何時載入技能 SOP 來回答客戶問題。
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from skills import load_skills, Skill
from skills.tools import load_skill, transfer_to_human, set_skills, build_skills_prompt

SYSTEM_PROMPT = """\
你是「鎖市」（LockSmart）的 AI 智慧鎖客服。你的職責是透過 LINE 回覆客戶關於電子鎖的問題。

## 核心原則

1. **親切簡潔**：用口語化的繁體中文回覆，不超過 3-5 句話（除非 SOP 步驟需要）。
2. **資訊不足必追問**：若客戶沒提供品牌、型號、症狀等關鍵資訊，務必先追問再回答。每次只問 1-2 個問題。
3. **技能驅動（重要！）**：
   - 收到問題時，先用 load_skill 載入對應的大類別技能（如 troubleshoot）
   - 若大類別技能指向某個子技能（如 load_skill("ts-door-stuck")），**你必須再次呼叫 load_skill 載入該子技能**，取得完整 SOP 後才能回覆
   - 不要只根據大類別的摘要回覆，一定要載入最細粒度的子技能 SOP
4. **不要猜測**：不確定的事不要亂答，可以說「這個問題我需要請專人為您確認」。
5. **安全優先**：絕不指導客戶拆開電路板、剪斷電線等危險操作。

## 轉接真人（重要！）

當客戶表達任何想跟真人對話的意圖時（例如「轉真人」「找專員」「我要找人工客服」「讓我跟人說話」「我不要跟機器人講」等），
你必須立即呼叫 transfer_to_human 工具，並將工具回傳的訊息**原封不動**回覆給客戶，不要自行改寫或摘要。

## 客服問診優先順序

1. 確認品牌（Dormakaba、Chainlock/Chatlock、Philips、Kaadas、Milre、AiLock）
2. 確認型號（或開門方式：把手下壓 vs 推拉）
3. 確認問題症狀

## 店家資訊速查（不需要載入技能即可回答）

- 電話：02-8601-9952
- LINE：@706mrped
- 地址：新北市林口區民富街 83 號 1 樓
- 營業：週一至週六 09:30-21:30

{skills_section}
"""


def build_agent(model, skills_dir: str | None = None):
    """建立 skill-based ReAct agent。

    Args:
        model: LangChain ChatModel instance
        skills_dir: .claude/skills/ 目錄路徑（None 用預設）

    Returns:
        compiled LangGraph agent
    """
    # 1. 載入技能
    skills = load_skills(skills_dir)
    set_skills(skills)

    # 2. 組裝 system prompt
    skills_section = build_skills_prompt(skills)
    prompt = SYSTEM_PROMPT.format(skills_section=skills_section)

    # 3. 建立 agent
    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=model,
        tools=[load_skill, transfer_to_human],
        prompt=prompt,
        checkpointer=checkpointer,
        name="smart_lock_agent",
    )

    return agent
