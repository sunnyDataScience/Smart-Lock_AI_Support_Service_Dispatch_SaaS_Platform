"""Webhook Idempotency Cleanup Cron — CR-0166 R1。

每日刪除 webhook_idempotency 中 processed_at > 7 天的列（TTL 由 CR-0001 §8 Q5
裁決＝7 天，LINE 最長重送 24h，buffer 充裕）。表在品牌庫，寫入由 agent gateway
負責（mark-first）；本 cron 只負責過期清理，控制表大小。

複製 media_retention_cron 模式：asyncio worker + distributed_lock ensure_leader
（多實例僅 leader 執行）+ startup delay。
"""

from __future__ import annotations

import asyncio
import logging
import os

from core.distributed_lock import ensure_leader as _ensure_leader
from core.observability import job_span

logger = logging.getLogger("api.webhook_idempotency_cleanup_cron")

DEFAULT_INTERVAL_S = int(os.getenv("WEBHOOK_IDEM_CLEANUP_INTERVAL", str(24 * 60 * 60)))
DEFAULT_STARTUP_DELAY_S = int(os.getenv("WEBHOOK_IDEM_CLEANUP_STARTUP_DELAY", "120"))
RETENTION_DAYS = int(os.getenv("WEBHOOK_IDEM_RETENTION_DAYS", "7"))


class WebhookIdempotencyCleanupCron:
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
            "WebhookIdempotencyCleanupCron started (interval=%ds, retention=%dd)",
            self._interval, RETENTION_DAYS,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("WebhookIdempotencyCleanupCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=self._startup_delay)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            if not await _ensure_leader("webhook_idempotency_cleanup_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                n = await self.run_once()
                if n:
                    logger.info("webhook-idem-cleanup tick: deleted %d expired rows", n)
            except Exception:  # noqa: BLE001
                logger.exception("webhook-idem-cleanup run_once failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> int:
        """刪除過期 webhook_idempotency 列，回筆數。"""
        # CR-0209 TC-NFR-OBS-01：背景 job 此前全樹零 span
        with job_span("cron.webhook_idempotency_cleanup"):
            import core.db as db_module
            from core.db import _ensure_conn

            if not await _ensure_conn():
                return 0
            cur = await db_module._conn.execute(
                "DELETE FROM webhook_idempotency "
                "WHERE processed_at < NOW() - (%s * INTERVAL '1 day')",
                (RETENTION_DAYS,),
            )
            return cur.rowcount or 0


# Singleton — main.py lifespan 引用
worker = WebhookIdempotencyCleanupCron()
