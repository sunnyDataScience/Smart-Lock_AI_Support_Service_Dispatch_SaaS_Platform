"""Webhook idempotency guard — LINE 重送防護（CR-0001 §8 Q5 / Phase C2）。

原狀：``app.py /webhook`` 業務邏輯失敗回 HTTP 5xx → LINE 自動重送 →
**無 idempotency 保護** → 同 event 處理多次 → 對話歷史污染、PC 重複、
token cost 翻倍（CR-0001 §1 / NFR-IDEMP-001）。

決議 (CR-0001 §8 Q5 = 選項 a)：用 ``webhook_idempotency`` 表，TTL 7 天，
PRIMARY KEY = LINE event.message.id（或 webhookEventId）。

API：
- ``init_db(config)`` — startup 呼叫，開 pool；表已由 Schema_cr0001 建好
- ``mark_processed(event_id)`` — 嘗試 INSERT；命中 unique → False (already seen)
- ``cleanup_loop()`` — 定期 DELETE 超過 7 天的列（背景 task）

Layering: harness 層；不可 import agent root。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool

from core.logging_config import get_logger

log = get_logger(__name__)


_pool: AsyncConnectionPool | None = None
_enabled = False
_ttl_days = 7
_cleanup_interval_s = 3600  # 每小時掃一次


async def init_db(config: dict | None = None) -> None:
    """開 pool。表已由 SQL/Schema_cr0001_integration_gaps.sql 建好，
    本函式不做 CREATE TABLE 以避免與 migration 衝突。"""
    global _pool, _enabled, _ttl_days, _cleanup_interval_s
    config = config or {}

    if not config.get("enabled", True):
        log.info("webhook_idempotency_disabled")
        _enabled = False
        return

    _ttl_days = int(config.get("ttl_days", 7))
    _cleanup_interval_s = int(config.get("cleanup_interval_s", 3600))

    pg_uri = os.environ.get(config.get("postgres_uri_env", "POSTGRES_URI"), "")
    if not pg_uri:
        log.warning("webhook_idempotency_no_pg_uri")
        _enabled = False
        return

    try:
        pool = AsyncConnectionPool(
            conninfo=pg_uri,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True},
            open=False,
            check=AsyncConnectionPool.check_connection,
        )
        await pool.open(wait=True)
        _pool = pool
        _enabled = True
        log.info("webhook_idempotency_enabled", ttl_days=_ttl_days)
    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("webhook_idempotency_db_failed", error=str(e))
        _enabled = False


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def mark_processed(
    event_id: str,
    *,
    source: str = "line",
    tenant_id: str = "default",
) -> bool:
    """嘗試標記 event_id 為已處理。

    Returns:
        True  — 首次見到此 event_id（caller 應繼續處理）
        False — 已存在（重送，caller 應跳過）

    若 DB 不可用（_enabled=False），預設回 True（**fail-open**）：寧可
    重複處理也不要靜默丟訊息。實務上 LINE webhook 重送機率 < 1%，
    fail-open 風險小於 fail-close 風險。
    """
    if not _enabled or _pool is None:
        return True
    try:
        async with _pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO webhook_idempotency (event_id, source, tenant_id) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (event_id) DO NOTHING "
                "RETURNING event_id",
                (event_id, source, tenant_id),
            )
            row = await cur.fetchone()
            # row=None → ON CONFLICT 命中（已存在）
            return row is not None
    except (psycopg.Error, OSError, RuntimeError) as e:
        log.warning("webhook_idempotency_mark_failed", event_id=event_id[:32], error=str(e))
        return True  # fail-open


async def cleanup_loop() -> None:
    """背景 task：定期清掉超過 TTL 的舊 entries。"""
    if not _enabled:
        return
    while True:
        try:
            await asyncio.sleep(_cleanup_interval_s)
            if _pool is None:
                continue
            async with _pool.connection() as conn:
                cur = await conn.execute(
                    f"DELETE FROM webhook_idempotency "
                    f"WHERE processed_at < NOW() - INTERVAL '{_ttl_days} days' "
                    f"RETURNING event_id"
                )
                rows = await cur.fetchall()
                if rows:
                    log.info("webhook_idempotency_cleaned", n=len(rows))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("webhook_idempotency_cleanup_failed", error=str(e))


__all__ = ["init_db", "close_db", "mark_processed", "cleanup_loop"]
