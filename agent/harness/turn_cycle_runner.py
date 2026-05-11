"""Turn Cycle runner — orchestrator 的單一進入點，包 fail-open fallback。

設計：
- 對外只暴露 ``run_belief_cycle(...)``，回傳 ``(belief_hint_str, action_type)``
- 內部 wrap dev 的 ``ChatLiteLLM`` 成 ``LLMCaller`` 介面
- Hypothesize 失敗（JSON 不合法 / LLM 逾時 / DB 寫入掛掉）→ log 後回 ``("", None)``
  讓 caller 走原 ReAct path（fail-open）
- ESCALATE 由 caller 決定是否旁路 ReAct，本模組不做副作用
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg_pool import AsyncConnectionPool

from core.logging_config import get_logger
from harness.belief_hint import render_belief_hint
from harness.turn_cycle import TurnCycleContext, run_pre_execute
from hypothesize import LLMCaller

log = get_logger(__name__)


# Hypothesize LLM call 的硬超時（秒）— 避免拖累 user 等回覆
_HYPOTHESIZE_TIMEOUT_S = 15


def wrap_langchain_llm(model: Any) -> LLMCaller:
    """把 LangChain ChatModel 包成 ``Callable[[str], Awaitable[str]]``。

    Args:
        model: ``llms.get_llm()`` 回傳的 ChatLiteLLM（或任何 LangChain ChatModel）

    Returns:
        async callable — 餵 prompt 回 response.content 字串
    """
    async def _caller(prompt: str) -> str:
        result = await model.ainvoke(prompt)
        content = getattr(result, "content", result)
        return content if isinstance(content, str) else str(content)
    return _caller


async def run_belief_cycle(
    *,
    user_id: str,
    user_message: str,
    history: list[dict],
    user_facts: dict[str, str],
    pool: AsyncConnectionPool,
    llm_model: Any,
    thread_id: str | None = None,
) -> tuple[str, str | None]:
    """跑 Hypothesize → Decide，回傳 (hint_prefix, action_type)。

    Fail-open：任何失敗都回 ``("", None)``，caller 直接走原 ReAct 不會掛掉。

    Args:
        user_id: LINE user id
        user_message: 本輪客戶訊息（純文字；多模態應在 caller 抽 text 部分）
        history: 最近對話歷史 [{"role": "user"|"assistant", "content": str}]
        user_facts: ProfileManager.load_facts() 的結果
        pool: PG 連線池（讀 prior belief + 寫新 belief）
        llm_model: LangChain ChatModel
        thread_id: belief 持久化用；預設等於 ``"line_{user_id}"``

    Returns:
        ``(belief_hint_string, action_type)``
        - ``hint_string`` — 渲染好的 [Belief Hint] 區塊，可直接拼進 prompt
          prefix；fail-open 時回 ``""``
        - ``action_type`` — ``"COMMIT" / "PROBE" / "EXPLORE" / "ESCALATE"``
          或 ``None``（fail-open）
    """
    tid = thread_id or f"line_{user_id}"
    ctx = TurnCycleContext(
        user_message=user_message,
        thread_id=tid,
        user_id=user_id,
        history=history,
        user_facts=user_facts,
    )
    llm = wrap_langchain_llm(llm_model)

    try:
        belief, decision = await asyncio.wait_for(
            run_pre_execute(ctx, pool=pool, llm=llm),
            timeout=_HYPOTHESIZE_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.warning("turn_cycle_timeout", user_id=user_id, timeout_s=_HYPOTHESIZE_TIMEOUT_S)
        return "", None
    except Exception as e:  # noqa: BLE001 — fail-open: 任何例外都退回原 path
        log.warning("turn_cycle_failed", user_id=user_id, error=str(e))
        return "", None

    hint = render_belief_hint(belief, decision)
    log.info(
        "turn_cycle_ok",
        user_id=user_id,
        turn_id=belief.turn_id,
        action=decision.action,
        top_conf=round(belief.top_confidence, 2),
    )
    return hint, decision.action
