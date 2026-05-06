"""對話記憶壓縮模組 — 當 messages 超過閾值時，用 LLM 摘要舊訊息。

流程：
  1. 讀取 checkpoint 中的 messages
  2. 若超過 max_messages_threshold → LLM 摘要舊訊息
  3. 用 RemoveMessage 刪除舊訊息，保留最近 N 輪
  4. 下次 ainvoke 時注入 [前情提要] 摘要

由 debounce.run_agent() 在 ainvoke 前呼叫。
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage

from core.config import load_prompt
from core.content_utils import extract_text
from harness.llm_metrics import log_simple


def _extract_text_from_content(content) -> str:
    """Backward-compatible wrapper around `core.content_utils.extract_text`.

    Preserves the legacy semantics of the original inline routine:
      * media blocks rendered as [傳送了圖片/音檔/影片] placeholders
      * empty fallback ("" instead of repr(content))
    Kept as a thin alias so existing call sites do not change.  RP1.C.3.
    """
    return extract_text(
        content, include_media_placeholder=True, fallback_to_repr=False
    )


# 模組層級狀態（由 init() 初始化）
_llm = None
_config: dict = {}
_profile_mgr = None

# 每個 thread 的摘要（in-memory，隨 checkpoint 生命週期）
_summaries: dict[str, str] = {}


def init(llm, config: dict, profile_mgr=None):
    """注入依賴，由 app.py startup 呼叫。

    Args:
        llm: LangChain ChatModel instance（用於摘要壓縮）
        config: memory config dict，需包含：
            - max_messages_threshold (int): 觸發壓縮的訊息數量閾值，default 20
            - context_retention_pair (int): 壓縮後保留的對話輪數，default 5
            - domain (str): 領域描述，注入摘要 prompt
        profile_mgr: ProfileManager instance（用於載入用戶輪廓）
    """
    global _llm, _config, _profile_mgr
    _llm = llm
    _config = config
    _profile_mgr = profile_mgr


async def maybe_compress(agent, thread_id: str, user_id: str = "") -> str | None:
    """檢查並壓縮過長的對話歷史。

    Args:
        agent: compiled LangGraph agent（用於 aget_state / aupdate_state）
        thread_id: 對話 thread ID
        user_id: 用戶 ID（用於載入 soft profile 注入摘要 prompt）

    Returns:
        摘要文字（若有壓縮），或 None（未觸發）
    """
    if not _llm or not _config.get("compression_enabled", True):
        return None

    threshold = _config.get("max_messages_threshold", 20)
    retention_pair = _config.get("context_retention_pair", 5)

    config = {"configurable": {"thread_id": thread_id}}

    # 讀取當前 checkpoint state
    state = await agent.aget_state(config)
    if not state.values:
        return None

    messages = state.values.get("messages", [])
    print(f"[Memory] 當前訊息數: {len(messages)} / 閾值: {threshold}")
    if len(messages) <= threshold:
        print(f"[Memory] 未超過閾值，跳過壓縮")
        return None

    print(f"[Memory] 訊息數 {len(messages)} > {threshold}，觸發壓縮...")

    # 計算要壓縮和保留的訊息
    keep_count = retention_pair * 2  # 每輪 = 1 human + 1 ai
    cut_index = len(messages) - keep_count

    # 確保切割點不會切斷 tool_call / tool_response 配對：
    # 往前找到第一個 HumanMessage 作為保留區起點
    while cut_index < len(messages):
        if getattr(messages[cut_index], "type", "") == "human":
            break
        cut_index += 1

    if cut_index >= len(messages):
        return None

    messages_to_summarize = messages[:cut_index]

    # 格式化對話文字
    dialogue_lines = []
    for msg in messages_to_summarize:
        role = getattr(msg, "type", "unknown")
        raw_content = getattr(msg, "content", "")
        if not raw_content or role == "tool":
            continue
        content = _extract_text_from_content(raw_content)
        if not content:
            continue
        if role == "human":
            dialogue_lines.append(f"使用者: {content}")
        elif role == "ai":
            dialogue_lines.append(f"客服: {content}")
        elif role == "system":
            dialogue_lines.append(f"系統: {content}")

    if not dialogue_lines:
        return None

    dialogue_text = "\n".join(dialogue_lines)

    # 產生摘要
    existing_summary = _summaries.get(thread_id, "")
    domain = _config.get("domain", "電子鎖、智慧門鎖")

    # 載入用戶 soft profile
    user_profile = ""
    if _profile_mgr and _profile_mgr.enabled and user_id:
        user_profile = await _profile_mgr.load_profile(user_id)

    summarize_prompt = load_prompt(
        _config.get("summarize_prompt", "prompts/summarize_messages.md"),
        domain=domain,
        existing_summary=existing_summary or "(無既有摘要)",
        user_profile=user_profile or "(無用戶輪廓)",
    )

    model_name = _config.get("model_name") or _config.get("compression_model") or "unknown"
    t0 = time.monotonic()
    try:
        response = await _llm.ainvoke([
            SystemMessage(content=summarize_prompt),
            HumanMessage(content=dialogue_text),
        ])
        latency_ms = int((time.monotonic() - t0) * 1000)
        log_simple(
            user_id=user_id or thread_id,
            call_site="memory_compression",
            model=model_name,
            response=response,
            latency_ms=latency_ms,
            user_question=dialogue_text,
            metadata={"thread_id": thread_id, "summarized_messages": len(messages_to_summarize)},
        )
        new_summary = response.content.strip()
    except Exception as e:
        log_simple(
            user_id=user_id or thread_id,
            call_site="memory_compression",
            model=model_name,
            latency_ms=int((time.monotonic() - t0) * 1000),
            success=False,
            error_type=type(e).__name__,
            user_question=dialogue_text,
        )
        print(f"[Memory] 摘要生成失敗: {e}")
        return None

    # 刪除舊訊息（透過 RemoveMessage）
    remove_messages = [RemoveMessage(id=msg.id) for msg in messages_to_summarize if hasattr(msg, "id") and msg.id]

    if remove_messages:
        await agent.aupdate_state(
            config,
            {"messages": remove_messages},
        )

    # 儲存摘要
    _summaries[thread_id] = new_summary
    print(f"[Memory] 壓縮完成：刪除 {len(remove_messages)} 則舊訊息，摘要 {len(new_summary)} 字")

    return new_summary


def get_summary(thread_id: str) -> str:
    """取得指定 thread 的摘要文字。"""
    return _summaries.get(thread_id, "")


def build_summary_prefix(summary: str) -> str:
    """將摘要格式化為注入 user message 的前綴。"""
    return (
        f"[前情提要]\n{summary}\n\n"
        "【注意】以上為歷史對話摘要，可能包含多個不同話題。"
        "請只參考與使用者「當前問題」直接相關的部分，"
        "忽略不相關的歷史話題，避免將不同主題的資訊混入回答。\n\n"
    )
