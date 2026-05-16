"""Outbox Worker — agent_outbox consumer (ADR-0029 / CR-0001 §1).

之前 admin_api.py 失敗時會 `_write_outbox` 寫入 agent_outbox 表，但沒有
consumer worker 撈出來重試，PC / Conversation 等資料永遠卡在 outbox。本
模組補上 consumer。

Design (CR-0001 §8 Q6, 決議採 option a)：
- 與 agent 同 process，由 app.py startup 起 background task
- Cloud Run min-instance=1 保證 worker 不死；獨立 job 留待量大再切

Layering: harness 層；可 import core / integrations / harness sibling；不可
import agent root（避免循環）。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool

from core.logging_config import get_logger

log = get_logger(__name__)


# 預設輪詢與重試參數（可由 config 覆蓋）
_DEFAULT_POLL_INTERVAL_S = 30
_DEFAULT_MAX_ATTEMPTS = 5
_DEFAULT_BATCH_SIZE = 10
# 'processing' 列被搶後超過此秒數仍未結束 → 視為前一個 worker crash，回收成 pending
_PROCESSING_STALE_S = 300


_running = False
_task: asyncio.Task | None = None


async def run_outbox_worker(
    pool: AsyncConnectionPool,
    *,
    base_url: str,
    bearer: str,
    tenant_id: str,
    poll_interval_s: int = _DEFAULT_POLL_INTERVAL_S,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> None:
    """主迴圈。由 app.py 透過 ``asyncio.create_task`` 起在背景。

    Loop logic：
    1. 回收 stale 'processing' 列 → 'pending'（前一輪 worker crash 時的孤兒）
    2. SELECT FOR UPDATE SKIP LOCKED 撈 batch 筆 pending → 標 'processing'
    3. 逐筆 re-issue HTTP；成功標 'succeeded'，失敗 attempts+1
    4. attempts >= max_attempts → 標 'failed' + alert
    5. sleep poll_interval_s
    """
    global _running
    _running = True
    log.info("outbox_worker_started", poll_s=poll_interval_s, max_attempts=max_attempts)

    while _running:
        try:
            await _recover_stale_processing(pool)
            entries = await _lease_pending(pool, batch_size)
            for entry in entries:
                await _process_entry(
                    pool, entry,
                    base_url=base_url, bearer=bearer, tenant_id=tenant_id,
                    max_attempts=max_attempts,
                )
        except asyncio.CancelledError:
            log.info("outbox_worker_cancelled")
            raise
        except Exception as e:  # noqa: BLE001 — worker 一掛全掛，所以兜底 log + 繼續
            log.error("outbox_worker_loop_error", error=str(e), exc_info=True)

        try:
            await asyncio.sleep(poll_interval_s)
        except asyncio.CancelledError:
            raise

    log.info("outbox_worker_stopped")


async def stop_outbox_worker() -> None:
    """app.py shutdown 呼叫，讓 main loop 跳出。"""
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass


def start_in_background(
    pool: AsyncConnectionPool,
    *,
    base_url: str,
    bearer: str,
    tenant_id: str,
    **kwargs: Any,
) -> asyncio.Task:
    """Helper：建立 task 並記錄 module-level 供 stop 用。"""
    global _task
    _task = asyncio.create_task(
        run_outbox_worker(
            pool,
            base_url=base_url, bearer=bearer, tenant_id=tenant_id,
            **kwargs,
        )
    )
    return _task


# ─────────────────────────────────────────────
# Internal
# ─────────────────────────────────────────────


async def _recover_stale_processing(pool: AsyncConnectionPool) -> None:
    """把 'processing' 但 updated_at 超過 stale TTL 的列退回 'pending'。"""
    async with pool.connection() as conn:
        await conn.execute(
            f"""
            UPDATE agent_outbox
               SET status = 'pending', updated_at = NOW()
             WHERE status = 'processing'
               AND updated_at < NOW() - INTERVAL '{_PROCESSING_STALE_S} seconds'
            """
        )


async def _lease_pending(
    pool: AsyncConnectionPool, batch_size: int
) -> list[dict]:
    """SELECT FOR UPDATE SKIP LOCKED 撈 batch 筆 pending，原子標 'processing'。

    用 RETURNING 一併取回需要的欄位，避免兩次 round-trip。
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            WITH leased AS (
                SELECT id
                  FROM agent_outbox
                 WHERE status = 'pending'
              ORDER BY created_at
                 LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE agent_outbox o
               SET status = 'processing', updated_at = NOW()
              FROM leased
             WHERE o.id = leased.id
         RETURNING o.id, o.flow_id, o.endpoint, o.payload, o.headers,
                   o.attempts, o.last_error
            """,
            (batch_size,),
        )
        rows = await cur.fetchall()

    entries = []
    for row in rows:
        entries.append({
            "id": row[0],
            "flow_id": row[1],
            "endpoint": row[2],
            "payload": row[3],
            "headers": row[4] or {},
            "attempts": row[5],
            "last_error": row[6],
        })
    return entries


async def _process_entry(
    pool: AsyncConnectionPool,
    entry: dict,
    *,
    base_url: str,
    bearer: str,
    tenant_id: str,
    max_attempts: int,
) -> None:
    """單筆重試。成功標 succeeded；失敗 attempts++（達 max → failed）。"""
    import httpx

    url = f"{base_url.rstrip('/')}{entry['endpoint']}"
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": tenant_id,
        "Content-Type": "application/json",
        # outbox 內的 headers 不含 Authorization（admin_api.py:178 已 strip）；
        # 我們在重試時補上自己的 bearer。
        **{k: v for k, v in entry["headers"].items() if k.lower() != "authorization"},
    }

    new_attempts = entry["attempts"] + 1
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=entry["payload"], headers=headers)
        if 200 <= res.status_code < 300:
            await _mark_succeeded(pool, entry["id"], attempts=new_attempts)
            log.info(
                "outbox_succeeded",
                outbox_id=str(entry["id"]),
                flow_id=entry["flow_id"],
                attempts=new_attempts,
            )
            return
        # 4xx 不可重試（業務錯誤）→ 直接標 failed，避免無止盡重試
        if 400 <= res.status_code < 500:
            await _mark_failed(
                pool, entry["id"], attempts=new_attempts,
                error=f"4xx no-retry {res.status_code} {res.text[:200]}",
            )
            log.error(
                "outbox_failed_4xx",
                outbox_id=str(entry["id"]),
                flow_id=entry["flow_id"],
                status=res.status_code,
            )
            return
        last_error = f"{res.status_code} {res.text[:200]}"
    except Exception as e:  # noqa: BLE001 — HTTP error / timeout / network
        last_error = f"{type(e).__name__}: {e}"

    # 5xx / network error → 視 attempts 決定 retry vs failed
    if new_attempts >= max_attempts:
        await _mark_failed(pool, entry["id"], attempts=new_attempts, error=last_error)
        log.error(
            "outbox_failed_max_attempts",
            outbox_id=str(entry["id"]),
            flow_id=entry["flow_id"],
            attempts=new_attempts,
            last_error=last_error[:200],
        )
        # TODO: 接 alerting channel（Slack / PagerDuty）通知主管處理
    else:
        await _mark_pending(pool, entry["id"], attempts=new_attempts, error=last_error)
        log.warning(
            "outbox_retry_scheduled",
            outbox_id=str(entry["id"]),
            attempts=new_attempts,
            last_error=last_error[:200],
        )


async def _mark_succeeded(pool: AsyncConnectionPool, id_: Any, *, attempts: int) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE agent_outbox SET status='succeeded', attempts=%s, "
            "last_error=NULL, updated_at=NOW() WHERE id=%s",
            (attempts, id_),
        )


async def _mark_pending(
    pool: AsyncConnectionPool, id_: Any, *, attempts: int, error: str
) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE agent_outbox SET status='pending', attempts=%s, "
            "last_error=%s, updated_at=NOW() WHERE id=%s",
            (attempts, error, id_),
        )


async def _mark_failed(
    pool: AsyncConnectionPool, id_: Any, *, attempts: int, error: str
) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE agent_outbox SET status='failed', attempts=%s, "
            "last_error=%s, updated_at=NOW() WHERE id=%s",
            (attempts, error, id_),
        )


__all__ = [
    "run_outbox_worker",
    "start_in_background",
    "stop_outbox_worker",
]
