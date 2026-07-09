"""Statement Auto-Approval Cron — Phase II MVP statement 三表 dispute window 過期自動 approve。

涵蓋表（FR-0045/0046/0047 共用 6 狀態機 + 7d dispute window pattern）：
  - saas.technician_statement (FR-0045)
  - saas.dispatcher_commission_statement (FR-0046)
  - saas.brand_b2b_statement (FR-0047)

規則：
  status = 'pending_review' AND dispute_window_ends_at < NOW()
  → status = 'approved', reviewed_by = NULL, reviewed_at = NOW()

審計：auto-approved 不寫 reviewed_by（NULL 表示系統自動，與人工 approve 區分）。

預設 interval：3600s (1 hr)。Statement window 7 天，1 hr 掃描足夠 timely。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.statement_auto_approval_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "STATEMENT_AUTO_APPROVAL_INTERVAL", str(60 * 60),  # 1 hr
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "STATEMENT_AUTO_APPROVAL_STARTUP_DELAY", "60",
))

# 3 statement 表共享相同 schema (status + dispute_window_ends_at)
_STATEMENT_TABLES = [
    "saas.technician_statement",
    "saas.dispatcher_commission_statement",
    "saas.brand_b2b_statement",
]


class StatementAutoApprovalCron:
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
            "StatementAutoApprovalCron started (interval=%ds, tables=%d)",
            self._interval, len(_STATEMENT_TABLES),
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("StatementAutoApprovalCron stopped")

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
            if not await _ensure_leader("statement_auto_approval_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                summary = await self.run_once()
                if any(v > 0 for v in summary.values() if isinstance(v, int)):
                    logger.info("auto-approval tick: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("auto-approval run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> dict:
        """掃 3 statement 表 → UPDATE 過期 pending_review → approved。

        Returns: {table_name: count, ...}
        """
        if not await _ensure_conn():
            return {"skipped": "db_unavailable"}

        summary: dict = {}
        for table in _STATEMENT_TABLES:
            try:
                count = await self._auto_approve_table(table)
                summary[table] = count
            except Exception:  # noqa: BLE001
                logger.exception("auto-approve failed for table %s", table)
                summary[table] = 0
                summary.setdefault("errors", 0)
                summary["errors"] += 1
        return summary

    async def _auto_approve_table(self, table: str) -> int:
        """UPDATE 單表所有過期 row → approved。返回 rowcount。"""
        sql = (
            f"UPDATE {table} SET "
            "  status = 'approved', "
            "  reviewed_at = NOW(), "
            "  updated_at = NOW() "
            "WHERE status = 'pending_review' "
            "  AND dispute_window_ends_at IS NOT NULL "
            "  AND dispute_window_ends_at < NOW()"
        )
        cur = await db_module._conn.execute(sql)
        count = cur.rowcount if hasattr(cur, "rowcount") else 0
        if count > 0:
            logger.info(
                "auto-approved %d %s rows (dispute window expired)",
                count, table,
            )
        return count


# Singleton — main.py lifespan 引用
worker = StatementAutoApprovalCron()
