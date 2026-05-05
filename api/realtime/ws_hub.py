"""WebSocket pub-sub hub（in-memory；單機 MVP）。

設計：
  - channel → set[WebSocket] 簡單映射，asyncio Lock 保護
  - publish(channel, payload) → 對該 channel 所有連線 send_json，失敗自動斷線回收
  - 多進程 / 多 worker 部署時需改用 Redis pub-sub（後續迭代）

頻道命名（對齊 docs/02-design/specs/asyncapi.yaml）：
  /realtime/notifications/{user_id}
  /realtime/work-orders/{id}
  /realtime/dispatch-queue
  /realtime/sla-alerts
  /realtime/refunds / /realtime/disputes / /realtime/inventory/low-stock / /realtime/rbac
  /realtime/pool/{tech_id}
  /realtime/diagnostics/{conv_id}（SSE，不在此 hub）

訊息格式：JSON `{ "type": "<event-name>", "payload": {...} }`
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("api.ws_hub")


class WSHub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(ws)
        logger.info("ws subscribe channel=%s subscribers=%d", channel, len(self._channels.get(channel, set())))

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs:
                subs.discard(ws)
                if not subs:
                    self._channels.pop(channel, None)
        logger.info("ws unsubscribe channel=%s remaining=%d", channel, len(self._channels.get(channel, set())))

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """對 channel 所有連線送出 JSON message。回傳成功 send 的 connection 數。"""
        async with self._lock:
            subs = list(self._channels.get(channel, set()))
        if not subs:
            return 0
        sent = 0
        dead: list[WebSocket] = []
        for ws in subs:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception as e:  # noqa: BLE001 — 任何錯誤都標 dead
                logger.warning("ws send failed channel=%s err=%s", channel, e)
                dead.append(ws)
        if dead:
            async with self._lock:
                bucket = self._channels.get(channel)
                if bucket:
                    for ws in dead:
                        bucket.discard(ws)
                    if not bucket:
                        self._channels.pop(channel, None)
        return sent

    def channel_count(self) -> int:
        return len(self._channels)


# 單例 hub（進程內共用）
hub = WSHub()
