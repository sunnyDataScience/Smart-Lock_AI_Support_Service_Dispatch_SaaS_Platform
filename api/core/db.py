"""共用 DB 連線（單一 AsyncConnection + autocommit + 自動重連）。

模式沿用 agent/profiles/manager.py 的 _ensure_conn() 設計，CloudSQL 閒置斷線可透明重連。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg import AsyncConnection

logger = logging.getLogger("api.db")

_conn: AsyncConnection | None = None
_uri_env: str = "POSTGRES_URI"


async def _ensure_conn() -> bool:
    global _conn
    if _conn is not None and not _conn.closed and not _conn.broken:
        return True
    uri = os.getenv(_uri_env)
    if not uri:
        logger.error("環境變數 %s 未設定", _uri_env)
        return False
    try:
        if _conn is not None:
            try:
                await _conn.close()
            except Exception as e:
                logger.warning("[DB] close 既有連線失敗（將以新連線取代）: %s", e, exc_info=True)
        _conn = await AsyncConnection.connect(uri, autocommit=True)
        logger.info("[DB] 已連線（autocommit=True, env=%s）", _uri_env)
        return True
    except Exception as e:
        logger.error("[DB] 連線失敗：%s", e)
        _conn = None
        return False


async def init_db(database_cfg: dict) -> None:
    global _uri_env
    _uri_env = database_cfg.get("postgres_uri_env", "POSTGRES_URI")
    await _ensure_conn()


async def close_db() -> None:
    global _conn
    if _conn is not None:
        try:
            await _conn.close()
        finally:
            _conn = None


async def healthcheck() -> bool:
    if not await _ensure_conn():
        return False
    try:
        cur = await _conn.execute("SELECT 1")
        await cur.fetchone()
        return True
    except Exception as e:
        logger.error("[DB] healthcheck 失敗：%s", e)
        return False


@asynccontextmanager
async def get_conn() -> AsyncIterator[AsyncConnection]:
    """以 context manager 形式取出共享連線。供 FastAPI dependency 使用。"""
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    yield _conn  # type: ignore[misc]
