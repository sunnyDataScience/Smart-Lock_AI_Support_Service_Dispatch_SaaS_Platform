"""GDPR Hard-Delete Cron — FR-0053 T+30 自動硬刪過期 forget_request。

對齊 FR-0053 BR-PII-001：T0 soft_delete → T+30 hard_delete (30 天 cooldown 後)。

cron 每日 (24h) 掃一次 soft_deleted + hard_delete_eligible_at <= NOW 的
forget_request → 呼 gdpr_forget_service.hard_delete 走完整流程
（DELETE users + UPDATE forget_request status='hard_deleted'）。

不直接寫 SQL — 走 service 確保 audit trail 一致。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.gdpr_hard_delete_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "GDPR_HARD_DELETE_INTERVAL", str(24 * 60 * 60),  # 1 day
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "GDPR_HARD_DELETE_STARTUP_DELAY", "60",
))
DEFAULT_BATCH_SIZE = int(os.getenv("GDPR_HARD_DELETE_BATCH", "50"))


class GdprHardDeleteCron:
    def __init__(
        self,
        interval_seconds: int = DEFAULT_INTERVAL_S,
        startup_delay_s: int = DEFAULT_STARTUP_DELAY_S,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._interval = interval_seconds
        self._startup_delay = startup_delay_s
        self._batch_size = batch_size
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "GdprHardDeleteCron started (interval=%ds, batch=%d)",
            self._interval, self._batch_size,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("GdprHardDeleteCron stopped")

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
            if not await _ensure_leader("gdpr_hard_delete_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                summary = await self.run_once()
                if summary.get("processed", 0) or summary.get("errors", 0):
                    logger.info("hard-delete tick: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("hard-delete run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> dict:
        """掃 soft_deleted + cooldown 過 → 呼 service.hard_delete。"""
        if not await _ensure_conn():
            return {"skipped": "db_unavailable", "processed": 0, "errors": 0}

        cur = await db_module._conn.execute(
            # tenant_id 必須一起撈 —— hard_delete 是 keyword-only 必填，
            # 漏了它整支 cron 每次執行都 TypeError（見下方呼叫處註解）。
            "SELECT id, tenant_id FROM saas.forget_request "
            "WHERE status = 'soft_deleted' "
            "  AND hard_delete_eligible_at IS NOT NULL "
            "  AND hard_delete_eligible_at <= NOW() "
            "ORDER BY hard_delete_eligible_at ASC "
            "LIMIT %s",
            (self._batch_size,),
        )
        rows = await cur.fetchall()
        processed = 0
        errors = 0
        for row in rows:
            request_id = str(row[0])
            try:
                from services import gdpr_forget_service
                await gdpr_forget_service.hard_delete(
                    request_id=request_id,
                    # ⚠️ 2026-08-05 修（CR-0207 步驟 0-1）：原本漏傳 tenant_id，
                    # 而 hard_delete 的簽名是 `*, request_id, tenant_id, actor_user_id=None`
                    # —— tenant_id 是 keyword-only **必填**。也就是這支 cron
                    # **每次執行都拋 TypeError，GDPR 硬刪從來沒有成功過**。
                    # 測試沒抓到是因為 test_gdpr_hard_delete_cron.py 的三個 fake
                    # 簽名也漏了 tenant_id（fake 與真實簽名不一致＝測試在說謊），
                    # 已於同一 commit 一併修正。
                    tenant_id=str(row[1]),
                    actor_user_id=None,  # NULL 表系統自動
                )
                processed += 1
                logger.info(
                    "GDPR hard-deleted forget_request=%s (cron auto)",
                    request_id[:8],
                )
            except Exception:  # noqa: BLE001
                errors += 1
                logger.exception(
                    "hard-delete failed for forget_request=%s", request_id,
                )
        return {"processed": processed, "errors": errors}


# Singleton — main.py lifespan 引用
worker = GdprHardDeleteCron()
