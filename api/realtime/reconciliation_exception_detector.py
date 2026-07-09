"""Reconciliation Exception Detector — CR-0018 Stage 3 cron daily 偵測（HD-5=c 雙保險 b 路徑）。

每日 (預設 02:00 對應 86400s 週期) 掃描 saas.reconciliation + saas.settlement 找
common anomalies → 呼叫 reconciliation_exception_service.detect_exception 寫入。

偵測規則（最小集，Stage 3 收尾用；未來業務增補可加 detector rule）：

  1. amount_mismatch
     reconciliation.status='approved' 但 settlement.amount ≠ reconciliation.technician_payout
     → exception_kind='amount_mismatch', amount_delta=settlement.amount - r.technician_payout

  2. orphan_settlement
     settlement.id 存在但 reconciliation 不存在或 status='disputed'
     → exception_kind='orphan_settlement'

  3. missing_invoice
     reconciliation.status='approved' 但無對應 settlement 列（一天前已該結算）
     → exception_kind='missing_invoice'

冪等：service.detect_exception 已依 (tenant + recon + kind + description) dedup，
重複跑 cron 不會炸 row。

啟動：main.py lifespan 內 `worker.start()`；停止：`await worker.stop()`。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.recon_exception_detector")

DEFAULT_INTERVAL_S = int(os.getenv(
    "RECON_EXCEPTION_DETECTOR_INTERVAL", str(24 * 60 * 60),  # 1 day
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "RECON_EXCEPTION_DETECTOR_STARTUP_DELAY", "60",
))


class ReconExceptionDetector:
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
            "ReconExceptionDetector started (interval=%ds, startup_delay=%ds)",
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
        logger.info("ReconExceptionDetector stopped")

    async def _run(self) -> None:
        # 啟動延遲（避開 cold start race）
        try:
            await asyncio.wait_for(
                self._stopping.wait(), timeout=self._startup_delay,
            )
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("reconciliation_exception_detector"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                summary = await self.run_once()
                logger.info("detector tick summary: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("detector run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> dict:
        """單次掃描入口（測試與手動 trigger 可直接呼）。"""
        if not await _ensure_conn():
            return {"skipped": "db_unavailable"}

        summary = {
            "amount_mismatch": 0,
            "orphan_settlement": 0,
            "missing_invoice": 0,
            "errors": 0,
        }
        try:
            summary["amount_mismatch"] = await self._detect_amount_mismatch()
        except Exception:  # noqa: BLE001
            summary["errors"] += 1
            logger.exception("amount_mismatch detector failed")
        try:
            summary["orphan_settlement"] = await self._detect_orphan_settlement()
        except Exception:  # noqa: BLE001
            summary["errors"] += 1
            logger.exception("orphan_settlement detector failed")
        try:
            summary["missing_invoice"] = await self._detect_missing_invoice()
        except Exception:  # noqa: BLE001
            summary["errors"] += 1
            logger.exception("missing_invoice detector failed")
        return summary

    async def _detect_amount_mismatch(self) -> int:
        """recon.status='approved' AND settlement.amount ≠ recon.technician_payout。"""
        from services import reconciliation_exception_service as exc_svc

        cur = await db_module._conn.execute(
            "SELECT r.id, r.tenant_id, r.technician_payout, s.amount, s.id "
            "FROM saas.reconciliation r "
            "JOIN saas.settlement s ON s.reconciliation_id = r.id "
            "WHERE r.status = 'approved' "
            "  AND s.amount IS NOT NULL "
            "  AND r.technician_payout IS NOT NULL "
            "  AND s.amount <> r.technician_payout "
            "LIMIT 500"
        )
        rows = await cur.fetchall()
        count = 0
        for r in rows:
            recon_id, tenant_id, payout, settled, sid = r
            delta = float(settled) - float(payout)
            await exc_svc.detect_exception(
                tenant_id=str(tenant_id),
                reconciliation_id=str(recon_id),
                exception_kind="amount_mismatch",
                description=(
                    f"settlement={settled} vs payout={payout} "
                    f"(settlement_id={str(sid)[:8]})"
                ),
                detected_by="cron_daily",
                amount_delta=delta,
            )
            count += 1
        return count

    async def _detect_orphan_settlement(self) -> int:
        """settlement 存在但 reconciliation 不存在 → orphan。"""
        from services import reconciliation_exception_service as exc_svc

        cur = await db_module._conn.execute(
            "SELECT s.id, s.tenant_id, s.reconciliation_id "
            "FROM saas.settlement s "
            "LEFT JOIN saas.reconciliation r ON r.id = s.reconciliation_id "
            "WHERE r.id IS NULL "
            "LIMIT 200"
        )
        rows = await cur.fetchall()
        count = 0
        for r in rows:
            sid, tenant_id, recon_id = r
            # orphan 沒有 reconciliation，但 detect_exception 要 reconciliation_id
            # NULL；schema 要求 NOT NULL — 用 settlement.reconciliation_id 雖然
            # FK 已 broken 但仍 reference legacy id
            await exc_svc.detect_exception(
                tenant_id=str(tenant_id),
                reconciliation_id=str(recon_id),
                exception_kind="orphan_settlement",
                description=f"settlement {str(sid)[:8]} 無對應 reconciliation",
                detected_by="cron_daily",
            )
            count += 1
        return count

    async def _detect_missing_invoice(self) -> int:
        """recon.status='approved' 已超過 1 天但無 settlement → missing。

        實務上 reconciliation 應在 approve 後立即 INSERT settlement（co_sign
        flow），延遲 > 1 day 是異常。
        """
        from services import reconciliation_exception_service as exc_svc

        cur = await db_module._conn.execute(
            "SELECT r.id, r.tenant_id, r.approved_at "
            "FROM saas.reconciliation r "
            "LEFT JOIN saas.settlement s ON s.reconciliation_id = r.id "
            "WHERE r.status = 'approved' "
            "  AND r.approved_at < (NOW() - INTERVAL '1 day') "
            "  AND s.id IS NULL "
            "LIMIT 200"
        )
        rows = await cur.fetchall()
        count = 0
        for r in rows:
            recon_id, tenant_id, approved_at = r
            await exc_svc.detect_exception(
                tenant_id=str(tenant_id),
                reconciliation_id=str(recon_id),
                exception_kind="missing_invoice",
                description=(
                    f"approved {approved_at.isoformat() if approved_at else '?'} "
                    f"無對應 settlement (> 24hr)"
                ),
                detected_by="cron_daily",
            )
            count += 1
        return count


# Singleton — main.py lifespan 引用
worker = ReconExceptionDetector()
