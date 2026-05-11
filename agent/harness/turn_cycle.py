"""Turn Cycle orchestrator — Hypothesize → Decide → (Execute) → (Calibrate)。

對齊新需求《AI客服 Harness設計策略》§5 Harness 架構。

本檔只實作 Hypothesize + Decide 兩段，把 Execute / Calibrate 留給 caller：
- Execute：依 ActionDecision 決定要答覆 / 載 mega-doc / 追問 / 轉真人，
  目前仍由 dev 既有 ReAct agent 跑（C-3 後續才整合）
- Calibrate：階段 P1 才實作（讀客戶下輪反應更新 belief）

呼叫方式：

    from harness.turn_cycle import TurnCycleContext, run_pre_execute

    ctx = TurnCycleContext(
        user_message="我家 AS850 加卡步驟",
        thread_id="line-user-123",
        user_id="line-user-123",
        history=[{"role": "user", "content": "..."}],
        user_facts={"device_brand": "Dormakaba", "device_model": "AS850"},
    )
    belief, action = await run_pre_execute(ctx, pool=pool, llm=my_llm_callable)
    # 之後 caller 依 action.action 跑 Execute 邏輯
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# 讓本模組從 harness/ 子目錄 import 上層 agent/ 模組
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg_pool import AsyncConnectionPool

from belief import BeliefState
from belief_store import save_belief, load_latest_belief
from hypothesize import HypothesizeInput, LLMCaller, hypothesize
from policy import ActionDecision, decide
from profiles.context import format_catalog_section


@dataclass
class TurnCycleContext:
    """單輪 Turn Cycle 的所有輸入。"""
    user_message: str
    thread_id: str
    user_id: str
    history: list[dict] = field(default_factory=list)
    user_facts: dict[str, str] = field(default_factory=dict)


def _format_user_facts_block(facts: dict[str, str]) -> str:
    if not facts:
        return ""
    lines = ["[用戶資料]"]
    for k, v in facts.items():
        if v:
            lines.append(f"- {k}：{v}")
    return "\n".join(lines)


async def run_pre_execute(
    ctx: TurnCycleContext,
    *,
    pool: AsyncConnectionPool,
    llm: LLMCaller,
    persist: bool = True,
) -> tuple[BeliefState, ActionDecision]:
    """跑完 Hypothesize + Decide 兩段。

    Args:
        ctx: 本輪輸入
        pool: PG 連線池（讀 prior belief + 寫新 belief）
        llm: Hypothesize 用的 async LLM caller
        persist: 是否把新 belief 寫進 DB（測試時可設 False）

    Returns:
        (belief, action) — caller 依 action.action 跑 Execute
    """
    prior = await load_latest_belief(pool, thread_id=ctx.thread_id)
    next_turn_id = (prior.turn_id + 1) if prior is not None else 0

    inp = HypothesizeInput(
        user_message=ctx.user_message,
        history=ctx.history,
        prior_belief=prior,
        catalog_block=format_catalog_section(ctx.user_facts),
        user_facts_block=_format_user_facts_block(ctx.user_facts),
    )
    belief = await hypothesize(inp, llm, turn_id=next_turn_id)

    if persist:
        await save_belief(
            pool,
            thread_id=ctx.thread_id,
            user_id=ctx.user_id,
            belief=belief,
        )

    action = decide(belief)
    return belief, action
