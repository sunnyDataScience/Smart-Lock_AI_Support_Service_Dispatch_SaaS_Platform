"""Turn Cycle orchestrator — Calibrate → Hypothesize → Decide → (Execute)。

對齊新需求《AI客服 Harness設計策略》§5 Harness 架構。

本檔現在實作 Calibrate + Hypothesize + Decide 三段，把 Execute 留給 caller：
- Execute：依 ActionDecision 決定要答覆 / 載 mega-doc / 追問 / 轉真人，
  目前仍由 dev 既有 ReAct agent 跑（透過 Belief-Augmented ReAct hint 引導）
- Calibrate：第 N 輪起跑（prior belief 存在時才有「上一輪假設對不對」可校準）

呼叫方式：

    from harness.turn_cycle import TurnCycleContext, run_pre_execute

    ctx = TurnCycleContext(
        user_message="不是這個",
        thread_id="line-user-123",
        user_id="line-user-123",
        history=[{"role": "user", "content": "..."}],
        user_facts={"device_brand": "Dormakaba", "device_model": "AS850"},
    )
    belief, action = await run_pre_execute(ctx, pool=pool, llm=my_llm_callable)
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
from calibrate import CalibrateInput, CalibrationSignal, calibrate
from hypothesize import HypothesizeInput, LLMCaller, hypothesize
from policy import ActionDecision, decide
from profiles.context import format_catalog_section

from core.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class TurnCycleContext:
    """單輪 Turn Cycle 的所有輸入。"""
    user_message: str
    thread_id: str
    user_id: str
    history: list[dict] = field(default_factory=list)
    user_facts: dict[str, str] = field(default_factory=dict)
    prior_ai_reply: str = ""  # 上輪 AI 給客戶的回覆，給 Calibrate 看上下文用


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

    # 1. Calibrate — 上輪有 belief 才跑（第 0 輪 prior=None 跳過）
    cal_signal: CalibrationSignal | None = None
    if prior is not None and prior.top is not None:
        try:
            cal_signal = await calibrate(
                CalibrateInput(
                    user_message=ctx.user_message,
                    prior_belief=prior,
                    prior_ai_reply=ctx.prior_ai_reply,
                ),
                llm,
            )
            log.info(
                "calibrate_ok",
                user_id=ctx.user_id,
                signal=cal_signal.signal,
                prior_top=prior.top.description[:60],
            )
        except ValueError as e:
            # Calibrate fail 不 fatal — 退回沒有 signal 的 Hypothesize
            log.warning("calibrate_failed", user_id=ctx.user_id, error=str(e))

    # 2. Hypothesize — 把 Calibrate signal 一併餵 LLM
    inp = HypothesizeInput(
        user_message=ctx.user_message,
        history=ctx.history,
        prior_belief=prior,
        catalog_block=format_catalog_section(ctx.user_facts),
        user_facts_block=_format_user_facts_block(ctx.user_facts),
        calibration_signal=cal_signal,
    )
    belief = await hypothesize(inp, llm, turn_id=next_turn_id)

    # 3. Persist
    if persist:
        await save_belief(
            pool,
            thread_id=ctx.thread_id,
            user_id=ctx.user_id,
            belief=belief,
        )

    # 4. Decide — 把 signal 傳進去讓 IMPATIENT 強制 ESCALATE
    action = decide(
        belief,
        calibration_signal=cal_signal.signal if cal_signal else None,
    )
    return belief, action
