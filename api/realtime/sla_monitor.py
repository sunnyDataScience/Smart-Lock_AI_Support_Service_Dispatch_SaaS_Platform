"""SLA 引擎 — 三類 service-level 告警背景偵測。

對應 docs/02-design/specs/asyncapi.yaml /realtime/sla-alerts。

三類 alert_type（spec 規範）：
  - quote_expiring     : 工單已 quoted（estimated_price 已設）但客戶長時間未確認
                          MVP 代理：work_orders.status='created' AND
                          estimated_price IS NOT NULL AND created > X 分
  - dispatch_delay     : 派工逾時 — work_orders.status IN ('created','assigned')
                          AND created_at < NOW() - X 分
  - response_overdue   : 客戶等待回覆超時 — conversations.status='active'
                          AND 最後一則訊息 role='user' AND created_at < NOW() - X 分

設計：
  - asyncio loop 定期掃（預設 60s，最小 30s）
  - in-memory _alerted dict[(alert_type, target_id)] 防止重複告警；
    狀態恢復後（解除條件不再成立）從 set 移除，下次再觸發
  - 環境變數：
    SLA_MONITOR_INTERVAL_SECONDS（預設 60）
    SLA_QUOTE_EXPIRING_MINUTES（預設 1440 = 24 小時）
    SLA_DISPATCH_DELAY_MINUTES（預設 30）
    SLA_RESPONSE_OVERDUE_MINUTES（預設 30）

對齊現有 InventoryMonitor 模式（v1.28.0）。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn

logger = logging.getLogger("api.sla_monitor")

DEFAULT_INTERVAL = max(30, int(os.environ.get("SLA_MONITOR_INTERVAL_SECONDS", "60")))
QUOTE_EXPIRING_MINUTES = int(os.environ.get("SLA_QUOTE_EXPIRING_MINUTES", "1440"))
DISPATCH_DELAY_MINUTES = int(os.environ.get("SLA_DISPATCH_DELAY_MINUTES", "30"))
RESPONSE_OVERDUE_MINUTES = int(os.environ.get("SLA_RESPONSE_OVERDUE_MINUTES", "30"))


class SLAMonitor:
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = interval_seconds
        # 用 (alert_type, target_id) 當 key
        self._alerted: set[tuple[str, str]] = set()
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "SLAMonitor started (interval=%ds, quote=%dm, dispatch=%dm, response=%dm)",
            self._interval,
            QUOTE_EXPIRING_MINUTES,
            DISPATCH_DELAY_MINUTES,
            RESPONSE_OVERDUE_MINUTES,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("SLAMonitor stopped")

    async def _run(self) -> None:
        # 啟動後等 5 秒再首次掃，避免與 startup 競爭
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            try:
                await self._scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("SLAMonitor scan_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval
                )
                return
            except asyncio.TimeoutError:
                continue

    async def _scan_once(self) -> None:
        if not await _ensure_conn():
            logger.warning("DB not available, skip SLA scan")
            return

        active_keys: set[tuple[str, str]] = set()
        new_alerts: list[dict] = []

        # ─── quote_expiring ───────────────────────────────────────────
        cur = await db_module._conn.execute(
            "SELECT id, created_at "
            "FROM work_orders "
            "WHERE status = 'created' "
            "  AND estimated_price IS NOT NULL "
            "  AND created_at < NOW() - (INTERVAL '1 minute' * %s)",
            (QUOTE_EXPIRING_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("quote_expiring", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "quote_expiring",
                        "target_id": target_id,
                        "threshold_minutes": QUOTE_EXPIRING_MINUTES,
                    }
                )

        # ─── dispatch_delay ───────────────────────────────────────────
        cur = await db_module._conn.execute(
            "SELECT id, status "
            "FROM work_orders "
            "WHERE status IN ('created', 'assigned') "
            "  AND created_at < NOW() - (INTERVAL '1 minute' * %s)",
            (DISPATCH_DELAY_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("dispatch_delay", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "dispatch_delay",
                        "target_id": target_id,
                        "threshold_minutes": DISPATCH_DELAY_MINUTES,
                    }
                )

        # ─── response_overdue ─────────────────────────────────────────
        # 抓 active 對話中、最後一則為 user 訊息且超過閾值
        cur = await db_module._conn.execute(
            "SELECT c.id "
            "FROM conversations c "
            "WHERE c.status = 'active' "
            "  AND EXISTS ( "
            "    SELECT 1 FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) "
            "  AND ( "
            "    SELECT m.role FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) = 'user' "
            "  AND ( "
            "    SELECT m.created_at FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) < NOW() - (INTERVAL '1 minute' * %s)",
            (RESPONSE_OVERDUE_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("response_overdue", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "response_overdue",
                        "target_id": target_id,
                        "threshold_minutes": RESPONSE_OVERDUE_MINUTES,
                    }
                )

        # 從 _alerted 移除已恢復（不再符合條件）的告警
        recovered = self._alerted - active_keys
        if recovered:
            logger.info("SLA recovered: %d alerts cleared", len(recovered))
        self._alerted = active_keys

        if not new_alerts:
            return

        try:
            from realtime.ws_hub import hub

            for alert in new_alerts:
                await hub.publish(
                    "/realtime/sla-alerts",
                    {"type": "sla.alert", "payload": alert},
                )
            logger.info(
                "SLA alerts pushed: %d new (quote=%d, dispatch=%d, response=%d)",
                len(new_alerts),
                sum(1 for a in new_alerts if a["alert_type"] == "quote_expiring"),
                sum(1 for a in new_alerts if a["alert_type"] == "dispatch_delay"),
                sum(1 for a in new_alerts if a["alert_type"] == "response_overdue"),
            )
        except Exception:  # noqa: BLE001
            logger.exception("ws publish sla.alert failed (non-fatal)")


# 單例
monitor = SLAMonitor()
