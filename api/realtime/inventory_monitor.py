"""庫存低水位背景偵測 job。

設計：
  - asyncio 定期 loop（預設 60 秒）掃描 inventory_items
  - 找出 quantity_on_hand <= reorder_point AND is_active=TRUE 的品項
  - 與上次掃描比對，只對「新進入低水位」的品項推 WS（避免每次掃描都重複轟炸）
  - 補貨後 quantity 回升 → 從 alerted set 移除（下次再低水位時會再推）
  - 環境變數：INVENTORY_MONITOR_INTERVAL_SECONDS（預設 60）

通道對齊 docs/02-design/specs/asyncapi.yaml /realtime/inventory/low-stock
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.inventory_monitor")

DEFAULT_INTERVAL = int(os.environ.get("INVENTORY_MONITOR_INTERVAL_SECONDS", "60"))


class InventoryMonitor:
    """單例：在 FastAPI lifespan 中啟動 .start() / .stop()。"""

    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = max(10, interval_seconds)
        self._alerted: set[str] = set()  # 已通知過的 item_id（避免重複）
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "InventoryMonitor started (interval=%ds)", self._interval
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("InventoryMonitor stopped")

    async def _run(self) -> None:
        # 啟動後等 5 秒再首次掃描，避免與 startup 競爭
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=5)
            return  # 啟動初期就被停
        except asyncio.TimeoutError:
            pass

        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("inventory_monitor"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                await self._scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("InventoryMonitor scan_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval
                )
                return  # 收到停止訊號
            except asyncio.TimeoutError:
                continue

    async def _scan_once(self) -> None:
        """掃描一次：找新進入低水位的品項，推 WS 並更新 alerted set。"""
        if not await _ensure_conn():
            logger.warning("DB not available, skip inventory scan")
            return
        cur = await db_module._conn.execute(
            "SELECT id, part_number, name, quantity_on_hand, reorder_point "
            "FROM inventory_items "
            "WHERE is_active = TRUE"
        )
        rows = await cur.fetchall()
        currently_low: set[str] = set()
        new_alerts: list[dict] = []
        for r in rows:
            item_id = str(r[0])
            qty = int(r[3])
            threshold = int(r[4])
            if qty <= threshold:
                currently_low.add(item_id)
                if item_id not in self._alerted:
                    new_alerts.append(
                        {
                            "part_id": item_id,
                            "part_number": r[1],
                            "name": r[2],
                            "current_stock": qty,
                            "threshold": threshold,
                        }
                    )
        # 從 alerted 移除已恢復的（下次再低水位會再推）
        recovered = self._alerted - currently_low
        if recovered:
            logger.info("inventory recovered: %d items", len(recovered))
        self._alerted = currently_low

        if not new_alerts:
            return

        try:
            from realtime.ws_hub import hub

            for alert in new_alerts:
                await hub.publish(
                    "/realtime/inventory/low-stock",
                    {"type": "low_stock", "payload": alert},
                )
            logger.info("inventory low-stock pushed: %d items", len(new_alerts))
        except Exception:  # noqa: BLE001
            logger.exception("ws publish low_stock failed (non-fatal)")


# 單例
monitor = InventoryMonitor()
