"""跨實例 cron 互斥（SA-02 / CR-0134）——PG advisory lock 領導者選舉。

設計（零新增基礎設施——鎖押在既有品牌庫連線的 session advisory lock）：
  - 每個背景 worker 每輪 tick 前呼 `ensure_leader(job)`：
      * 本 session 已持鎖 → True（快取，不重複 acquire——PG advisory lock 同
        session 重複 try 會堆疊計數）
      * 未持 → `pg_try_advisory_lock(NS, crc32(job))`：搶到＝本實例為該 job leader
      * 沒搶到 → False（他實例在跑；本實例待命，下一輪再試）
  - **failover**：leader 實例死亡 → session 斷線 → PG 自動釋放 → 待命實例
    下一輪 `ensure_leader` 接手。無需心跳/續租。
  - DB 不可用 → True（單機 degraded 模式照跑——cron 多為 DB 作業，DB 掛了
    tick 本身也會 fail-soft；寧可雙跑風險也不可全停）。
"""

from __future__ import annotations

import logging
import zlib

import core.db as db_module
from core.db import _ensure_conn

logger = logging.getLogger("api.distributed_lock")

# advisory lock 命名空間（int32；與其他系統性 advisory 用途區隔）
_LOCK_NS = 0x5A02  # "SA-02"

# 本 session 已持有的 job 鎖（防同 session 重複 acquire 堆疊）
_held: set[str] = set()


def _job_key(job: str) -> int:
    """job 名 → int32 key（crc32 截 31 bit，避免負數跨語言歧義）。"""
    return zlib.crc32(job.encode("utf-8")) & 0x7FFFFFFF


async def ensure_leader(job: str) -> bool:
    """本實例是否為 job 的 leader（詳見模組 docstring）。絕不 raise。"""
    if job in _held:
        return True
    try:
        if not await _ensure_conn():
            return True  # DB 不可用 → 單機 degraded，照跑
        cur = await db_module._conn.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (_LOCK_NS, _job_key(job)),
        )
        row = await cur.fetchone()
        got = bool(row and row[0])
        if got:
            _held.add(job)
            logger.info("cron leader acquired: %s（本實例接手排程）", job)
        return got
    except Exception:  # noqa: BLE001 — 鎖機制故障不可癱瘓 cron；退單機語意
        logger.exception("ensure_leader(%s) 異常——退單機語意照跑", job)
        return True


async def release_leader(job: str) -> None:
    """顯式讓出（測試/優雅關閉用；正常依賴 session 斷線自動釋放）。"""
    if job not in _held:
        return
    try:
        await db_module._conn.execute(
            "SELECT pg_advisory_unlock(%s, %s)", (_LOCK_NS, _job_key(job)),
        )
    except Exception:  # noqa: BLE001
        logger.warning("release_leader(%s) 失敗（session 斷線時會自動釋放）", job)
    finally:
        _held.discard(job)
