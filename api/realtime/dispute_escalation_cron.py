"""Dispute 60d 自動 escalation cron — AC-03（解 WBS §8 P1 缺口）。

解凍 `dispute_v2_service._escalate_overdue_disputes` 從 [DEFERRED] helper
→ 接 in-process cron。每日掃 sla_deadline < NOW 且 status IN
(filed, in_review, mediation) 的 dispute → status=escalated +
escalated_to='ops_director' + escalated_at=NOW。

對齊 SLAMonitor / LinePushOutboxWorker / ReconExceptionDetector pattern：
  - 86400s (24h) 預設 interval（env: DISPUTE_ESCALATION_CRON_INTERVAL）
  - 60s 啟動延遲避 cold-start race
  - try/except 隔離；不阻 lifespan
  - run_once 入口可供 admin manual trigger（測試 + 緊急修補）
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.dispute_escalation_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "DISPUTE_ESCALATION_CRON_INTERVAL", str(24 * 60 * 60),  # 1 day
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "DISPUTE_ESCALATION_CRON_STARTUP_DELAY", "60",
))


class DisputeEscalationCron:
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
        logger.info(
            "DisputeEscalationCron started (interval=%ds, startup_delay=%ds)",
            self._interval, self._startup_delay,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("DisputeEscalationCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(
                self._stopping.wait(), timeout=self._startup_delay,
            )
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("dispute_escalation_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                count = await self.run_once()
                logger.info("dispute escalation tick: %d disputes", count)
            except Exception:  # noqa: BLE001
                logger.exception("dispute escalation run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self, *, tenant_id: str | None = None) -> int:
        """跑一次 60d escalation；回傳升級筆數。可供 admin manual trigger。"""
        if not await _ensure_conn():
            return 0

        where_clauses = [
            "status IN ('filed', 'in_review', 'mediation')",
            "sla_deadline < NOW()",
        ]
        args: list = []
        if tenant_id:
            where_clauses.append("tenant_id = %s::uuid")
            args.append(tenant_id)

        sql = (
            "UPDATE saas.dispute SET "
            "  status = 'escalated', "
            "  escalated_to = 'ops_director', "
            "  escalated_at = NOW() "
            f"WHERE {' AND '.join(where_clauses)}"
        )
        cur = await db_module._conn.execute(sql, tuple(args))
        count = cur.rowcount if hasattr(cur, "rowcount") else 0
        if count > 0:
            logger.info(
                "dispute auto-escalation: %d disputes (tenant=%s)",
                count, tenant_id,
            )
        return count


# Singleton — main.py lifespan 引用
worker = DisputeEscalationCron()
