"""CR-0196 回覆延遲三項改動的守線測試（mock provider，不打 API）。

背景（prod log 實測，20 個 turn 樣本）：
  端到端 109.8s（Turn A）；BUILD 中位數 8.5s、RUN 25.0s、SAVE 8.1s。
  BUILD 的歷史壓縮與 SAVE 的記憶抽取都是 LLM，且都在「回覆送出」之前——
  客人等的有一大半不是答案。另 reply-guard 20 輪觸發 4 次（20%），
  每次讓整輪 agent loop 重跑。

本檔鎖住三件事，避免日後被改回去：
  S1  SAVE 的記憶抽取不得阻塞 turn（改 _schedule_background）
  S3  BUILD 不得再阻塞跑歷史壓縮（SAVE 末尾已有背景版）
  S2  reply-guard 重生必須是「無工具的單次 LLM 呼叫」，不是整輪 agent loop
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from lockcore.agent.loop import AgentLoop
from lockcore.agent.user_memory import MemoryManager, SqliteMemoryProvider
from lockcore.bus.events import InboundMessage
from lockcore.bus.queue import MessageBus
from lockcore.providers.base import LLMProvider, LLMResponse


class _CountingProvider(LLMProvider):
    """記錄每次 chat 的 tools 參數與呼叫次數；可指定逐次回覆內容。"""

    def __init__(self, replies: list[str] | None = None):
        super().__init__()
        self._replies = list(replies or ["好的，已為您記下。"])
        self.calls: list[dict[str, Any]] = []

    def get_default_model(self) -> str:
        return "mock-model"

    async def chat(
        self, messages, tools=None, model=None, max_tokens: int = 4096,
        temperature: float = 0.7, reasoning_effort=None, tool_choice=None,
    ) -> LLMResponse:
        self.calls.append({"tools": tools, "n_messages": len(messages)})
        content = self._replies[min(len(self.calls) - 1, len(self._replies) - 1)]
        return LLMResponse(content=content, finish_reason="stop")


def _make_loop(tmp_path, mgr, provider=None):
    return AgentLoop(
        bus=MessageBus(),
        provider=provider or _CountingProvider(),
        workspace=tmp_path,
        model="mock-model",
        memory_manager=mgr,
        memory_tenant="locksmart",
    )


# ── S1：記憶抽取不得阻塞回覆 ────────────────────────────────────────────────


class _SlowExtractMemoryManager(MemoryManager):
    """把記憶抽取拖慢，用來量「turn 有沒有等它」。"""

    def __init__(self, provider, delay: float):
        super().__init__(provider)
        self._delay = delay
        self.recorded = False

    async def record_turn_async(self, *a, **kw):
        await asyncio.sleep(self._delay)
        self.recorded = True
        return super().record_turn(*a, **kw)


@pytest.mark.asyncio
async def test_save_memory_does_not_block_turn(tmp_path):
    """慢速記憶抽取不得拖慢 turn —— 這是 CR-0196 的核心主張。

    抽取設 2 秒；turn 必須在遠短於此的時間內返回。改回 `await` 就會紅。
    """
    mgr = _SlowExtractMemoryManager(SqliteMemoryProvider(":memory:"), delay=2.0)
    loop = _make_loop(tmp_path, mgr)
    msg = InboundMessage(
        channel="cli", sender_id="userLatency", chat_id="userLatency",
        content="你好",
    )
    t0 = time.monotonic()
    out = await loop._process_message(msg, session_key="locksmart:userLatency")
    elapsed = time.monotonic() - t0
    assert out is not None
    assert elapsed < 1.0, (
        f"turn 耗時 {elapsed:.2f}s —— 記憶抽取（2s）被算進客人的等待時間了"
    )


@pytest.mark.asyncio
async def test_save_memory_still_eventually_written(tmp_path):
    """移出關鍵路徑 ≠ 不做。背景 task 仍須完成寫入。"""
    mgr = _SlowExtractMemoryManager(SqliteMemoryProvider(":memory:"), delay=0.05)
    loop = _make_loop(tmp_path, mgr)
    msg = InboundMessage(
        channel="cli", sender_id="userBg", chat_id="userBg",
        content="我家的鎖是 Dormakaba AS701",
    )
    await loop._process_message(msg, session_key="locksmart:userBg")
    for _ in range(50):            # 給背景 task 最多 ~1s 完成
        if mgr.recorded:
            break
        await asyncio.sleep(0.02)
    assert mgr.recorded, "記憶抽取被移出關鍵路徑後就再也沒被執行"


@pytest.mark.asyncio
async def test_memory_extraction_failure_never_breaks_turn(tmp_path):
    """抽取炸掉只能吞在背景，不得讓 turn 失敗（原行為的等價保證）。"""

    class _BoomManager(MemoryManager):
        async def record_turn_async(self, *a, **kw):
            raise RuntimeError("模擬抽取器炸裂")

    loop = _make_loop(tmp_path, _BoomManager(SqliteMemoryProvider(":memory:")))
    msg = InboundMessage(
        channel="cli", sender_id="userBoom", chat_id="userBoom", content="你好",
    )
    out = await loop._process_message(msg, session_key="locksmart:userBoom")
    assert out is not None, "記憶抽取失敗不該影響回覆"
    await asyncio.sleep(0.05)      # 讓背景 task 跑完，確認不會炸出未捕捉例外


# ── S3：BUILD 不得阻塞跑歷史壓縮 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_does_not_block_on_consolidation(tmp_path):
    """BUILD 阻塞 await 壓縮 → prod 中位數 8.5s。改動後該路徑不得再阻塞。

    把 consolidator 拖慢 2 秒；turn 仍須快速返回。
    注意 SAVE 末尾**仍會**以 _schedule_background 排一次（那是刻意保留的），
    所以這裡只驗「不阻塞」，不驗「不呼叫」。
    """
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    loop = _make_loop(tmp_path, mgr)

    original = loop.consolidator.maybe_consolidate_by_tokens

    async def _slow(*a, **kw):
        await asyncio.sleep(2.0)
        return await original(*a, **kw)

    loop.consolidator.maybe_consolidate_by_tokens = _slow  # type: ignore[assignment]
    msg = InboundMessage(
        channel="cli", sender_id="userConsol", chat_id="userConsol", content="你好",
    )
    t0 = time.monotonic()
    await loop._process_message(msg, session_key="locksmart:userConsol")
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, (
        f"turn 耗時 {elapsed:.2f}s —— 歷史壓縮（2s）又被 await 回關鍵路徑了"
    )


# ── S2：reply-guard 重生必須便宜 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guard_regen_is_single_toolless_call(tmp_path):
    """重生不得再跑整輪 agent loop。

    第一次回覆講出未溯源型號 → guard 觸發 → 重生。
    斷言：重生那一次 provider 呼叫帶 tools=None（＝不可能再跑工具迴圈）。
    """
    prov = _CountingProvider(replies=[
        "您的 Yale YDM4109 支援指紋喔",   # 違規：客人沒提過這個型號
        "這部分我為您轉接專員確認 🙏",     # 重生：乾淨
    ])
    mgr = MemoryManager(SqliteMemoryProvider(":memory:"))
    loop = _make_loop(tmp_path, mgr, provider=prov)
    msg = InboundMessage(
        channel="cli", sender_id="userGuard", chat_id="userGuard",
        content="我家的鎖打不開",
    )
    out = await loop._process_message(msg, session_key="locksmart:userGuard")
    assert out is not None
    assert len(prov.calls) >= 2, "guard 應該有觸發重生"
    regen = prov.calls[-1]
    assert regen["tools"] is None, (
        "重生仍帶著工具清單 → 會再跑一輪 agent loop，等於沒省到"
    )
