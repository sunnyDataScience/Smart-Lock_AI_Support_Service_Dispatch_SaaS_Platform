"""Statement Generate Cron — CR-0117 S4 技師月結 draft 自動產生。

先前月結完全靠 ops 手動 POST :generate（金額也手填），造成 saas.technician_statement
長期 0 筆、師傅端首頁「需注意」的對帳單區塊永遠空。本 worker 讓上個月有完工單的
技師自動拿到 draft：

規則（每 tick）：
  目標期間 = 上個自然月（月結在期間結束後才產生）。
  候選 = 該期間有完工單（completion_status IN completed/closed，對齊 CR-0106 佣金口徑）
         的 (tenant_id, technician_id) 組合。
  逐一呼叫 generate_statement(gross_amount=None → 依佣金口徑自動計算)；
  同 tech+period 已存在 → service 冪等直接回 existing（重跑安全）。

產生的是 **draft**（不自動 submit）—— 送審/核准仍走人工流程，保留 ops 覆核點。
預設 interval 6h：冪等 + 只補缺，頻率只影響「月初多快拿到 draft」。
隨 main.py `_RUN_BACKGROUND_WORKERS` 只在 dispatch/all surface 啟動（tech/platform 面不跑）。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date

import core.db as db_module
from core.db import _ensure_conn

logger = logging.getLogger("api.statement_generate_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "STATEMENT_GENERATE_INTERVAL", str(6 * 60 * 60),  # 6 hr
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "STATEMENT_GENERATE_STARTUP_DELAY", "120",
))

# 與 technician_commission_service._COMPLETED_STATUSES 對齊（佣金口徑）
_COMPLETED_STATUSES = ["completed", "closed"]


def _previous_month(today: date) -> tuple[int, int]:
    """回傳上個自然月 (year, month)。"""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """[month_start, next_month_start)。"""
    start = date(year, month, 1)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, nxt


class StatementGenerateCron:
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
            "StatementGenerateCron started (interval=%ds)", self._interval,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("StatementGenerateCron stopped")

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
                if summary.get("generated", 0):
                    logger.info("statement generate tick: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("statement generate run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self, *, today: date | None = None) -> dict:
        """對上個月有完工單、尚無 statement 的技師補產 draft。

        Returns: {"period": "YYYY-MM", "candidates": N, "generated": M, "errors": E}
        """
        if not await _ensure_conn():
            return {"skipped": "db_unavailable"}

        year, month = _previous_month(today or date.today())
        start, nxt = _month_bounds(year, month)

        # 候選：期間內有完工單的 (tenant, technician)；排除已有該期 statement 者
        cur = await db_module._conn.execute(
            "SELECT DISTINCT wo.tenant_id, wo.technician_id "
            "FROM work_orders wo "
            "WHERE wo.technician_id IS NOT NULL "
            "  AND wo.completion_status = ANY(%s) "
            "  AND wo.completed_at >= %s AND wo.completed_at < %s "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM saas.technician_statement s "
            "    WHERE s.tenant_id = wo.tenant_id "
            "      AND s.technician_id = wo.technician_id "
            "      AND s.period_year = %s AND s.period_month = %s"
            "  )",
            (_COMPLETED_STATUSES, start, nxt, year, month),
        )
        rows = await cur.fetchall()

        generated = 0
        errors = 0
        # lazy import 避免啟動期循環相依
        from services import technician_statement_service

        for tenant_id, technician_id in rows:
            try:
                await technician_statement_service.generate_statement(
                    tenant_id=str(tenant_id),
                    technician_id=str(technician_id),
                    period_year=year,
                    period_month=month,
                    # gross/completed 省略 → 依 CR-0106 佣金口徑自動計算
                    notes="[系統月結自動產生]",
                )
                generated += 1
            except Exception:  # noqa: BLE001 — 單一技師失敗不擋整批
                errors += 1
                logger.exception(
                    "auto-generate statement failed tech=%s %d-%02d",
                    str(technician_id)[:8], year, month,
                )
        return {
            "period": f"{year}-{month:02d}",
            "candidates": len(rows),
            "generated": generated,
            "errors": errors,
        }


# Singleton — main.py lifespan 引用
worker = StatementGenerateCron()
