"""Media Retention Cron — CR-0040 BR-M09-03：每日軟刪過期 evidence。

cron 每日掃一次 media_files.retention_until < NOW 且未軟刪者 → 標 deleted_at
（HD-4 軟刪，可復原 + audit）。走 media_service 確保邏輯一致。
保存期：一般 1 年、客訴/保固 2 年（Q027；於 upload 時依 purpose/WO 算入 retention_until）。
"""

from __future__ import annotations

import asyncio
import logging
import os
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.media_retention_cron")

DEFAULT_INTERVAL_S = int(os.getenv("MEDIA_RETENTION_INTERVAL", str(24 * 60 * 60)))  # 1 day
DEFAULT_STARTUP_DELAY_S = int(os.getenv("MEDIA_RETENTION_STARTUP_DELAY", "90"))


class MediaRetentionCron:
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
        logger.info("MediaRetentionCron started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("MediaRetentionCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=self._startup_delay)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("media_retention_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                n = await self.run_once()
                if n:
                    logger.info("media-retention tick: soft-deleted %d expired media", n)
            except Exception:  # noqa: BLE001
                logger.exception("media-retention run_once failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> int:
        """軟刪過期 media，回筆數。"""
        from services import media_service

        return await media_service.soft_delete_expired_media()


# Singleton — main.py lifespan 引用
worker = MediaRetentionCron()
