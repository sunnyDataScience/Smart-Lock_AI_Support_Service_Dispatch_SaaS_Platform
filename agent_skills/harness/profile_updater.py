"""用戶輪廓自動萃取模組 — 每次對話後用 LLM 萃取個資並更新。

由 debounce.agent_and_reply() 在取得 AI 回覆後呼叫。
不影響回覆速度（背景非阻塞執行）。
"""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import load_prompt

# 模組層級狀態（由 init() 初始化）
_llm = None
_config: dict = {}
_profile_mgr = None


def init(llm, config: dict, profile_mgr):
    """注入依賴，由 app.py startup 呼叫。

    Args:
        llm: LangChain ChatModel instance
        config: user_profile config dict
        profile_mgr: ProfileManager instance
    """
    global _llm, _config, _profile_mgr
    _llm = llm
    _config = config
    _profile_mgr = profile_mgr


async def extract_and_update(user_id: str, question: str, answer: str):
    """從對話中萃取個資並更新 user profile。

    Args:
        user_id: 使用者 ID
        question: 使用者問題（合併後的文字）
        answer: AI 回覆
    """
    if not _llm or not _profile_mgr or not _profile_mgr.enabled:
        return

    try:
        # 載入現有 profile
        existing_profile = await _profile_mgr.load_full_profile(user_id)

        domain = _config.get("domain", "電子鎖、智慧門鎖")
        fact_attrs = ", ".join(_config.get("fact_attributes", ["phone", "address", "device_model", "device_brand"]))

        prompt_path = _config.get("update_profile_prompt", "prompts/update_profile.md")
        prompt = load_prompt(
            prompt_path,
            domain=domain,
            existing_profile=existing_profile if existing_profile else "(empty - new user)",
            question=question,
            answer=answer,
            fact_attributes=fact_attrs,
        )

        response = await _llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"使用者: {question}\n客服: {answer}"),
        ])
        raw_text = response.content.strip()

        # 清除 code fence
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw_text)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            parsed = json.loads(cleaned)

            # 寫入 hard_facts（PostgreSQL SCD Type 2）
            hard_facts = parsed.get("hard_facts", {})
            if hard_facts and isinstance(hard_facts, dict):
                for key, val in hard_facts.items():
                    if val is not None and str(val).strip():
                        await _profile_mgr.update_fact(user_id, key, str(val).strip())
                        print(f"  [Profile] fact 寫入: {key}={val}")

            # 寫入 soft_profile（.md 檔案）— 暫時停用
            # soft_profile = parsed.get("soft_profile")
            # if soft_profile and isinstance(soft_profile, str) and len(soft_profile.strip()) >= 10:
            #     await _profile_mgr.save_profile(user_id, soft_profile.strip())
            #     print(f"  [Profile] 已更新 {user_id} 的軟輪廓")

        except json.JSONDecodeError:
            print("  [Profile] JSON 解析失敗，跳過")
            # 軟輪廓 fallback 暫時停用
            # if raw_text and len(raw_text) >= 10:
            #     await _profile_mgr.save_profile(user_id, raw_text)

    except Exception as e:
        print(f"  [Profile] 更新輪廓失敗: {e}")
