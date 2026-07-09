"""Auto-Confirm Cron — CR-0038 桶4 / Q063：客戶未回 48h 自動結案。

cron 每小時掃一次 work_orders.status='completed' 且 completed_at 超過 N 小時
（config auto_confirm_policy.hours，預設 48）→ 自動 confirmed/closed。
排除 high_risk_hold 與有 open exception_case 的單（客訴/爭議/保固由人工處理）。
走 work_order_service.auto_confirm_stale_completed 確保邏輯一致。
"""

from __future__ import annotations

import asyncio
import logging
import os
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.auto_confirm_cron")

DEFAULT_INTERVAL_S = int(os.getenv("AUTO_CONFIRM_INTERVAL", str(60 * 60)))  # 1 hour
DEFAULT_STARTUP_DELAY_S = int(os.getenv("AUTO_CONFIRM_STARTUP_DELAY", "120"))


class AutoConfirmCron:
    def __init__(
        self,
        interval_seconds: int = DEFAULT_INTERVAL_S,
        startup_delay_s: int = DEFAULT_STARTUP_DELAY_S,
    ) -> None:
        self._interval = interval_seconds
        self._startup_delay = startup_delay_s
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info("AutoConfirmCron started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("AutoConfirmCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=self._startup_delay)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("auto_confirm_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                n = await self.run_once()
                if n:
                    logger.info("auto-confirm tick: %d stale-completed WO auto-confirmed", n)
            except Exception:  # noqa: BLE001
                logger.exception("auto-confirm run_once failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> int:
        """自動結案逾期 completed WO，回筆數。"""
        from services import work_order_service

        return await work_order_service.auto_confirm_stale_completed()


# Singleton — main.py lifespan 引用
worker = AutoConfirmCron()
