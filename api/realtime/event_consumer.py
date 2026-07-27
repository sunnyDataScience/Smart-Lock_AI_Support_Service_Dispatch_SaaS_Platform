"""技師平台 CQRS 投影 consumer（CR-0166 R4 / ADR-017）。

訂閱各品牌 workorder.lifecycle / commission.accrued 事件 → 維護技師視角投影
（technician_workorder_projection / technician_commission_projection，lock_tech 自有）。

opt-in：KAFKA_BOOTSTRAP 未設 → 不啟動（no-op）。事件冪等：event_id dedup（跨重啟安全）。
handler 為純邏輯（吃 event dict + conn），可單測；transport（aiokafka loop）分離。

跑在技師平台（API_SURFACE=tech）——與 producer（品牌 dispatch 面）分離。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module

logger = logging.getLogger("api.event_consumer")

_TOPICS = ("workorder.lifecycle", "commission.accrued")
_CONSUMER_GROUP = os.getenv("EVENT_CONSUMER_GROUP", "technician-platform-projection")


def enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP"))


async def _tech_conn():
    """技師權威庫連線（投影落此）；單庫 fallback 回主連線。"""
    return await db_module.require_tech_conn()


async def ensure_schema() -> None:
    """建投影表（IF NOT EXISTS，opt-in 自持）。"""
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[2] / "SQL" / "tech_authority"
              / "Schema_cqrs_projection.sql").read_text(encoding="utf-8")
    conn = await _tech_conn()
    await conn.execute(schema)


async def _already_processed(conn, event_id: str, topic: str) -> bool:
    """event_id 是否已成功處理過（**唯讀**）。

    CR-0188：原本這裡是 `INSERT ... ON CONFLICT DO NOTHING` 兼作「查詢＋佔位」，
    但共用連線是 `autocommit=True`（core/db.py），dedup 列在 handler 執行**之前**
    就已提交 —— handler 一旦失敗（broker/DB 瞬斷、欄位缺漏…），該 event_id 就
    **永久被判定為已處理**，重播變 no-op，該筆投影再也補不回來（不可逆資料遺失）。
    原註解寫「單事件失敗只 log，不中斷消費（可後續重播）」，但重播其實不可能。

    改為唯讀查詢，標記移到 handler 成功之後（見 `_mark_processed`）。
    """
    cur = await conn.execute(
        "SELECT 1 FROM event_consumer_dedup WHERE event_id = %s", (event_id,))
    return await cur.fetchone() is not None


async def _mark_processed(conn, event_id: str, topic: str) -> None:
    """handler 成功後才記 dedup（CR-0188）。

    與唯讀檢查搭配會有「同一事件並發重投」的競態窗口，但兩個 handler 都是
    `ON CONFLICT ... DO UPDATE` 冪等 upsert（technician_workorder_projection /
    technician_commission_projection），重複套用結果相同 —— 相較於「永久遺失投影」，
    這個取捨明確更安全。ON CONFLICT DO NOTHING 讓並發標記本身也不會炸。
    """
    await conn.execute(
        "INSERT INTO event_consumer_dedup (event_id, topic) VALUES (%s, %s) "
        "ON CONFLICT (event_id) DO NOTHING",
        (event_id, topic),
    )


async def handle_workorder_lifecycle(conn, event: dict) -> None:
    """workorder.lifecycle → upsert 工單投影（欄位最小化）。"""
    await conn.execute(
        "INSERT INTO technician_workorder_projection "
        "  (work_order_id, tenant_id, technician_id, status, document_number, "
        "   district, scheduled_time, last_event_type, occurred_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (work_order_id) DO UPDATE SET "
        "  technician_id = EXCLUDED.technician_id, status = EXCLUDED.status, "
        "  document_number = EXCLUDED.document_number, district = EXCLUDED.district, "
        "  scheduled_time = EXCLUDED.scheduled_time, "
        "  last_event_type = EXCLUDED.last_event_type, "
        "  occurred_at = EXCLUDED.occurred_at, updated_at = NOW()",
        (
            event.get("work_order_id"), event.get("tenant_id"),
            event.get("technician_id"), event.get("status"),
            event.get("document_number"), event.get("district"),
            event.get("scheduled_time"), event.get("event_type"),
            event.get("occurred_at"),
        ),
    )


async def handle_commission_accrued(conn, event: dict) -> None:
    """commission.accrued → upsert 佣金投影（跨品牌 accrued 明細）。"""
    await conn.execute(
        "INSERT INTO technician_commission_projection "
        "  (settlement_id, tenant_id, reconciliation_id, technician_id, "
        "   amount, currency, accrued_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s) "
        "ON CONFLICT (settlement_id) DO UPDATE SET "
        "  amount = EXCLUDED.amount, currency = EXCLUDED.currency, "
        "  accrued_at = EXCLUDED.accrued_at",
        (
            event.get("settlement_id"), event.get("tenant_id"),
            event.get("reconciliation_id"), event.get("technician_id"),
            event.get("amount"), event.get("currency", "TWD"),
            event.get("accrued_at"),
        ),
    )


_HANDLERS = {
    "workorder.lifecycle": handle_workorder_lifecycle,
    "commission.accrued": handle_commission_accrued,
}


async def process_event(topic: str, event: dict) -> bool:
    """單事件處理（冪等＋dispatch handler）。回 True＝已處理；False＝重複/無 handler/失敗。"""
    handler = _HANDLERS.get(topic)
    if handler is None:
        return False
    event_id = event.get("event_id")
    conn = await _tech_conn()
    try:
        if event_id and await _already_processed(conn, event_id, topic):
            return False  # 重複，skip
        await handler(conn, event)
        # CR-0188：**成功之後**才記 dedup —— 先記會讓失敗事件永久無法重播
        if event_id:
            await _mark_processed(conn, event_id, topic)
        return True
    except Exception:  # noqa: BLE001 — 單事件失敗只 log，不中斷消費（可後續重播）
        logger.exception("process_event 失敗 topic=%s event_id=%s", topic, event_id)
        return False


class EventConsumerWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._consumer = None

    def start(self) -> None:
        if not enabled() or (self._task and not self._task.done()):
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info("EventConsumerWorker started (topics=%s)", _TOPICS)

    async def stop(self) -> None:
        self._stopping.set()
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:  # noqa: BLE001
                pass
            self._consumer = None
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                self._task.cancel()
            self._task = None
        logger.info("EventConsumerWorker stopped")

    async def _run(self) -> None:
        import json

        from aiokafka import AIOKafkaConsumer

        try:
            await ensure_schema()
        except Exception:  # noqa: BLE001
            logger.exception("投影 schema 建立失敗；consumer 退出")
            return
        try:
            self._consumer = AIOKafkaConsumer(
                *_TOPICS,
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP"),
                group_id=_CONSUMER_GROUP,
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode()),
            )
            await self._consumer.start()
        except Exception:  # noqa: BLE001
            logger.exception("EventConsumer start 失敗（投影將不更新，事件保留於 broker）")
            self._consumer = None
            return
        try:
            async for msg in self._consumer:
                if self._stopping.is_set():
                    break
                await process_event(msg.topic, msg.value or {})
        except Exception:  # noqa: BLE001
            logger.exception("EventConsumer 迴圈異常")
        finally:
            if self._consumer is not None:
                await self._consumer.stop()
                self._consumer = None


worker = EventConsumerWorker()
