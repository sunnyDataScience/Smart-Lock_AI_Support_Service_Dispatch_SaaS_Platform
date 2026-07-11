"""Kafka/Redpanda 事件骨幹 client（CR-0166 R4 / ADR-006 / ADR-017）。

D2 裁決：Redpanda（Kafka wire protocol 相容，走標準 aiokafka client，未來可換原生 Kafka）。

設計原則：
- **opt-in**：`KAFKA_BOOTSTRAP` 未設 → producer no-op（回 False），行為同 Kafka 前
  （outbox 保底路徑仍生效）。與 REDIS_URL/PLATFORM_POSTGRES_URI 同 fail-open 哲學。
- **fail-soft**：發事件失敗只 log，絕不阻斷業務交易（雙寫過渡：DB outbox 為保底）。
- **event_id 冪等**：每事件帶 event_id（consumer 端去重），對齊 webhook_idempotency pattern。

Topic（見 CR-0166-R4-event-backbone-design §2）：
  workorder.lifecycle / commission.accrued / technician.lifecycle
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger("api.event_bus")

TOPIC_WORKORDER_LIFECYCLE = "workorder.lifecycle"
TOPIC_COMMISSION_ACCRUED = "commission.accrued"
TOPIC_TECHNICIAN_LIFECYCLE = "technician.lifecycle"


def bootstrap_servers() -> str | None:
    return os.getenv("KAFKA_BOOTSTRAP") or None


def enabled() -> bool:
    return bootstrap_servers() is not None


class EventBusProducer:
    """單例 producer（lazy start）。KAFKA_BOOTSTRAP 未設 → 全 no-op。"""

    def __init__(self) -> None:
        self._producer: Any = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if not enabled() or self._started:
            return
        async with self._lock:
            if self._started:
                return
            try:
                from aiokafka import AIOKafkaProducer

                self._producer = AIOKafkaProducer(
                    bootstrap_servers=bootstrap_servers(),
                    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
                    key_serializer=lambda k: (k or "").encode(),
                    enable_idempotence=True,  # broker 端去重（producer 重試不重複）
                    acks="all",
                )
                await self._producer.start()
                self._started = True
                logger.info("EventBusProducer started (bootstrap=%s)", bootstrap_servers())
            except Exception:  # noqa: BLE001 — broker 不可達不可癱瘓 api 啟動
                logger.exception("EventBusProducer start 失敗（事件發送將 no-op，outbox 保底）")
                self._producer = None
                self._started = False

    async def stop(self) -> None:
        if self._producer is not None:
            try:
                await self._producer.stop()
            except Exception:  # noqa: BLE001
                logger.warning("EventBusProducer stop 失敗", exc_info=True)
            self._producer = None
            self._started = False

    async def publish(
        self, topic: str, payload: dict, *, key: str | None = None,
        event_id: str | None = None,
    ) -> bool:
        """發一則事件。回 True＝已送 broker；False＝未啟用/失敗（fail-soft，outbox 保底）。

        payload 自動補 event_id（冪等鍵）與 topic；key 用於 partition 分派（同 key 同序）。
        """
        if not enabled():
            return False
        if not self._started:
            await self.start()
        if self._producer is None:
            return False
        body = {"event_id": event_id or str(uuid.uuid4()), **payload}
        try:
            await self._producer.send_and_wait(topic, value=body, key=key)
            return True
        except Exception:  # noqa: BLE001 — 發送失敗只 log，業務交易不回滾（雙寫保底）
            logger.warning("event publish 失敗 topic=%s（outbox 保底）", topic, exc_info=True)
            return False


# 單例——main.py lifespan start/stop；service 層 import 使用
producer = EventBusProducer()


async def publish_event(
    topic: str, payload: dict, *, key: str | None = None, event_id: str | None = None,
) -> bool:
    """便捷發事件（fail-soft）。service 層呼叫；未啟用/失敗回 False，不 raise。"""
    return await producer.publish(topic, payload, key=key, event_id=event_id)
