"""M18 Phase II — canary rollout 自動 stage advance cron。

解凍 `config_m18_service._advance_canary_stage`（已從 [DEFERRED]
stub 升級為真實實作）。每 5 分鐘掃所有 `current_stage IN ('5%','50%')
AND next_stage_eta < NOW` 的 config_rollout → 呼 service helper 推進。

SLO halt（觀察 SLO 指標決定 rollback）仍 DEFERRED — 涉 metrics
collection + threshold 判斷，本輪只解 stage advance 缺口。

對齊既有 worker pattern (SLAMonitor / LinePushOutboxWorker /
ReconExceptionDetector / DisputeEscalationCron):
  - 300s (5 min) 預設 interval（env: CONFIG_CANARY_ADVANCE_INTERVAL）
  - 30s 啟動延遲
  - try/except per-rollout 隔離；不阻 lifespan
  - run_once 公開可呼供 admin manual trigger
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn

logger = logging.getLogger("api.config_canary_advance_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "CONFIG_CANARY_ADVANCE_INTERVAL", "300",  # 5 min
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "CONFIG_CANARY_ADVANCE_STARTUP_DELAY", "30",
))


class ConfigCanaryAdvanceCron:
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
            "ConfigCanaryAdvanceCron started (interval=%ds, startup_delay=%ds)",
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
        logger.info("ConfigCanaryAdvanceCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(
                self._stopping.wait(), timeout=self._startup_delay,
            )
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            try:
                summary = await self.run_once()
                if summary["advanced"] or summary["errors"]:
                    logger.info("canary advance tick: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("canary advance run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> dict:
        """掃所有 due rollout → 呼 service.advance；回 summary。"""
        if not await _ensure_conn():
            return {"skipped": "db_unavailable", "advanced": 0, "errors": 0}

        cur = await db_module._conn.execute(
            """
            SELECT id FROM saas.config_rollout
            WHERE strategy = 'canary_5_50_100'
              AND current_stage IN ('5%', '50%')
              AND next_stage_eta IS NOT NULL
              AND next_stage_eta < NOW()
            ORDER BY next_stage_eta
            LIMIT 100
            """,
        )
        rows = await cur.fetchall()
        advanced = 0
        errors = 0
        for row in rows:
            rollout_id = str(row[0])
            try:
                from services import config_m18_service
                result = await config_m18_service._advance_canary_stage(
                    rollout_id=rollout_id,
                )
                advanced += 1
                logger.info(
                    "canary advanced: rollout=%s new_stage=%s",
                    rollout_id[:8], result["new_stage"],
                )
            except Exception:  # noqa: BLE001
                errors += 1
                logger.exception("canary advance failed: rollout=%s", rollout_id)
        # CR-0059 / BR-M18-02：順帶啟用到期的排程 config（effective_at<=now 的 draft）
        scheduled = 0
        try:
            from services import config_m18_service
            scheduled = await config_m18_service.activate_due_scheduled()
            if scheduled:
                logger.info("scheduled config activated: %d", scheduled)
        except Exception:  # noqa: BLE001
            logger.exception("activate_due_scheduled failed")
        return {"advanced": advanced, "errors": errors, "scheduled_activated": scheduled}


# Singleton — main.py lifespan 引用
worker = ConfigCanaryAdvanceCron()
