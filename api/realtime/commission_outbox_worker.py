"""佣金事件 outbox worker — CR-0189。

`reconciliation_service.approve_reconciliation` 在**同交易**內寫入
`settlements` 與 `commission_event_outbox`，commit 後立即嘗試 publish。
即時 publish 失敗（Kafka 未啟用／瞬斷）時 outbox row 留 `pending`，
由本 worker 依 backoff 重送 —— 取代原本「publish 失敗只 logger.exception」
的**永久事件遺失**。

送達語意 at-least-once：重送時原樣帶入 outbox 持有的 `event_id`，消費端
`event_consumer._already_processed` 才擋得住重複（CR-0188 已把 dedup 改成
「handler 成功後才標記」，失敗可重播）。兩個 handler 皆為 ON CONFLICT
DO UPDATE 冪等 upsert，重複套用結果相同。

啟動：main.py lifespan（`_RUN_BACKGROUND_WORKERS` 為真時）`worker.start()`。

⚠️ 本 worker 跑在 lifespan 背景任務中，**不經 DBPoolScopeMiddleware**，用的是
   `db_module._conn` 共用連線。因此**只能下單語句**、絕不可開 `transaction()`
   —— 顯式 BEGIN 會把同時間其他請求在同一條連線上的語句一併捲進本交易。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.commission_outbox_worker")

DEFAULT_INTERVAL = int(os.getenv("COMMISSION_OUTBOX_WORKER_INTERVAL", "20"))  # seconds
BATCH_SIZE = int(os.getenv("COMMISSION_OUTBOX_WORKER_BATCH", "50"))
# Exponential backoff seconds 對應 attempts=1..6：30s / 2min / 8min / 30min / 2hr / 6hr
# max_attempts 預設 8（migration 119）→ 末兩次沿用 6hr，總覆蓋約 21 小時。
_BACKOFF_SECONDS_BY_ATTEMPT = [30, 120, 480, 1800, 7200, 21600]


class CommissionOutboxWorker:
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "CommissionOutboxWorker started (interval=%ds, batch=%d)",
            self._interval, BATCH_SIZE,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("CommissionOutboxWorker stopped")

    async def _run(self) -> None:
        # 啟動後等 5 秒避開 startup 競爭
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：多實例只有 leader 送，避免同一 row 被重複 publish。
            # （dedup 在消費端仍是保底，但發送端先收斂可省掉大量重複流量）
            if not await _ensure_leader("commission_outbox_worker"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                await self._poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("CommissionOutboxWorker poll_once failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                return
            except asyncio.TimeoutError:
                continue

    async def _poll_once(self) -> None:
        """取一批到期 pending row → 逐一重送。"""
        if not await _ensure_conn():
            logger.warning("DB not available, skip commission outbox poll")
            return

        # 刻意不用 FOR UPDATE SKIP LOCKED：共用連線是 autocommit，列鎖在語句結束即釋放，
        # 寫了也擋不住任何東西（既有 line_push_outbox_worker 就是這個誤導性寫法）。
        # 真正的互斥來自上方 ensure_leader；殘餘重複由消費端 event_id dedup 承接。
        cur = await db_module._conn.execute(
            "SELECT id, event_id, topic, event_key, payload, attempts, max_attempts "
            "FROM commission_event_outbox "
            "WHERE status = 'pending' AND next_attempt_at <= NOW() "
            "ORDER BY next_attempt_at ASC "
            "LIMIT %s",
            (BATCH_SIZE,),
        )
        rows = await cur.fetchall()
        if not rows:
            return

        for row in rows:
            await self._process_row(row)

    async def get_job_sli(self) -> dict[str, float | int]:
        """由 durable outbox 讀 oldest pending 與 dead-letter 累計。"""
        if not await _ensure_conn():
            return {}
        cur = await db_module._conn.execute(
            "SELECT "
            "COALESCE(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - "
            "  MIN(created_at) FILTER (WHERE status = 'pending'))), 0), "
            "count(*) FILTER (WHERE status = 'dead') "
            "FROM commission_event_outbox"
        )
        row = await cur.fetchone()
        return {
            "oldest_pending_seconds": max(0.0, float(row[0] or 0)),
            "retry_exhausted_total": int(row[1] or 0),
        }

    async def _process_row(self, row: tuple) -> None:
        outbox_id = str(row[0])
        event_id = str(row[1])
        topic = row[2]
        event_key = row[3]
        payload = row[4] if isinstance(row[4], dict) else {}
        attempts = int(row[5])
        max_attempts = int(row[6])

        try:
            from core.event_bus import publish_event
            ok = await publish_event(topic, payload, key=event_key, event_id=event_id)
            err = None if ok else "publish_event 回 False（event bus 未啟用或投遞失敗）"
        except Exception as exc:  # noqa: BLE001
            ok, err = False, f"{type(exc).__name__}: {exc}"

        if ok:
            await self._mark_sent(outbox_id)
            logger.info(
                "commission outbox 重送成功: id=%s topic=%s event_id=%s",
                outbox_id, topic, event_id,
            )
        else:
            await self._mark_failed(outbox_id, attempts, max_attempts, err or "")
            logger.warning(
                "commission outbox 重送失敗: id=%s topic=%s attempts=%d err=%s",
                outbox_id, topic, attempts + 1, err,
            )

    async def _mark_sent(self, outbox_id: str) -> None:
        await db_module._conn.execute(
            "UPDATE commission_event_outbox SET "
            "  status = 'sent', sent_at = NOW(), updated_at = NOW(), "
            "  attempts = attempts + 1 "
            "WHERE id = %s::uuid",
            (outbox_id,),
        )

    async def _mark_failed(
        self, outbox_id: str, current_attempts: int, max_attempts: int, err: str,
    ) -> None:
        new_attempts = current_attempts + 1
        if new_attempts >= max_attempts:
            await self._mark_dead(outbox_id, err)
            return
        backoff_idx = min(new_attempts - 1, len(_BACKOFF_SECONDS_BY_ATTEMPT) - 1)
        next_at = datetime.now(timezone.utc) + timedelta(
            seconds=_BACKOFF_SECONDS_BY_ATTEMPT[backoff_idx],
        )
        await db_module._conn.execute(
            "UPDATE commission_event_outbox SET "
            "  attempts = %s, next_attempt_at = %s, last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (new_attempts, next_at.isoformat(), err[:500], outbox_id),
        )

    async def _mark_dead(self, outbox_id: str, err: str) -> None:
        """耗盡重試 → dead。**settlement 已存在、款照付**，遺失的只是跨庫投影同步；
        由 OPS 撈 status='dead' 人工重放（保留 event_id 故重放仍冪等）。"""
        await db_module._conn.execute(
            "UPDATE commission_event_outbox SET "
            "  status = 'dead', attempts = attempts + 1, last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (err[:500], outbox_id),
        )
        logger.error(
            "commission outbox 進 dead（需人工重放）: id=%s err=%s", outbox_id, err[:200],
        )


# Singleton — main.py lifespan 引用
worker = CommissionOutboxWorker()
