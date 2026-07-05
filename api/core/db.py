"""共用 DB 連線（AsyncConnection + autocommit + 自動重連）。

模式沿用 agent/profiles/manager.py 的 _ensure_conn() 設計，CloudSQL 閒置斷線可透明重連。

CR-0112 方案 B（技師身分庫物理拆分）+ CR-0114（platform console）：本模組支援三條連線 ——
  - 主連線（POSTGRES_URI）：品牌營運庫（工單/派工/帳務/後台帳號）。
  - 技師庫連線（TECH_POSTGRES_URI）：技師身分域（users 技師列/technicians/
    排班/品牌授權/認證/技能/lifecycle 事件）。
  - 平台庫連線（PLATFORM_POSTGRES_URI）：平台方自有資料（platform_admin 帳號/
    revoked_jti/品牌申請 brand_applications）。
**Fallback 安全閥**：TECH_POSTGRES_URI / PLATFORM_POSTGRES_URI 未設定時，
get_tech_conn() / require_platform_conn() 直接回主連線 —— 單庫部署（現行雲端/
CI/pytest）行為與拆分前完全相同；設定後才是真多庫。
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

_tech_conn: AsyncConnection | None = None
_TECH_URI_ENV: str = "TECH_POSTGRES_URI"

_platform_conn: AsyncConnection | None = None
_PLATFORM_URI_ENV: str = "PLATFORM_POSTGRES_URI"


async def _ensure_conn() -> bool:
    global _conn
    # getattr 防禦:單元測試以假連線(無 closed/broken 屬性)monkeypatch _conn,
    # 視為健康直接沿用(真 psycopg 連線兩屬性必存在)。
    if _conn is not None and not getattr(_conn, "closed", False) and not getattr(_conn, "broken", False):
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


def tech_db_enabled() -> bool:
    """TECH_POSTGRES_URI 是否已配置（真雙庫模式）。"""
    return bool(os.getenv(_TECH_URI_ENV))


async def _ensure_tech_conn() -> bool:
    """技師庫連線；僅在 TECH_POSTGRES_URI 已設時使用（懶連線 + 自動重連）。"""
    global _tech_conn
    if _tech_conn is not None and not getattr(_tech_conn, "closed", False) and not getattr(_tech_conn, "broken", False):
        return True
    uri = os.getenv(_TECH_URI_ENV)
    if not uri:
        return False
    try:
        if _tech_conn is not None:
            try:
                await _tech_conn.close()
            except Exception as e:
                logger.warning("[TechDB] close 既有連線失敗（將以新連線取代）: %s", e, exc_info=True)
        _tech_conn = await AsyncConnection.connect(uri, autocommit=True)
        logger.info("[TechDB] 已連線（autocommit=True, env=%s）", _TECH_URI_ENV)
        return True
    except Exception as e:
        logger.error("[TechDB] 連線失敗：%s", e)
        _tech_conn = None
        return False


def platform_db_enabled() -> bool:
    """PLATFORM_POSTGRES_URI 是否已配置（platform console 專屬庫，CR-0114）。"""
    return bool(os.getenv(_PLATFORM_URI_ENV))


async def _ensure_platform_conn() -> bool:
    """平台庫連線；僅在 PLATFORM_POSTGRES_URI 已設時使用（懶連線 + 自動重連）。"""
    global _platform_conn
    if _platform_conn is not None and not getattr(_platform_conn, "closed", False) and not getattr(_platform_conn, "broken", False):
        return True
    uri = os.getenv(_PLATFORM_URI_ENV)
    if not uri:
        return False
    try:
        if _platform_conn is not None:
            try:
                await _platform_conn.close()
            except Exception as e:
                logger.warning("[PlatformDB] close 既有連線失敗（將以新連線取代）: %s", e, exc_info=True)
        _platform_conn = await AsyncConnection.connect(uri, autocommit=True)
        logger.info("[PlatformDB] 已連線（autocommit=True, env=%s）", _PLATFORM_URI_ENV)
        return True
    except Exception as e:
        logger.error("[PlatformDB] 連線失敗：%s", e)
        _platform_conn = None
        return False


async def init_db(database_cfg: dict) -> None:
    global _uri_env
    _uri_env = database_cfg.get("postgres_uri_env", "POSTGRES_URI")
    await _ensure_conn()
    if tech_db_enabled():
        await _ensure_tech_conn()
    if platform_db_enabled():
        await _ensure_platform_conn()


async def close_db() -> None:
    global _conn, _tech_conn, _platform_conn
    if _conn is not None:
        try:
            await _conn.close()
        finally:
            _conn = None
    if _tech_conn is not None:
        try:
            await _tech_conn.close()
        finally:
            _tech_conn = None
    if _platform_conn is not None:
        try:
            await _platform_conn.close()
        finally:
            _platform_conn = None


async def healthcheck() -> bool:
    if not await _ensure_conn():
        return False
    try:
        cur = await _conn.execute("SELECT 1")
        await cur.fetchone()
    except Exception as e:
        logger.error("[DB] healthcheck 失敗：%s", e)
        return False
    # 雙庫模式下技師庫也要活，否則回報 degraded
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            return False
        try:
            cur = await _tech_conn.execute("SELECT 1")
            await cur.fetchone()
        except Exception as e:
            logger.error("[TechDB] healthcheck 失敗：%s", e)
            return False
    if platform_db_enabled():
        if not await _ensure_platform_conn():
            return False
        try:
            cur = await _platform_conn.execute("SELECT 1")
            await cur.fetchone()
        except Exception as e:
            logger.error("[PlatformDB] healthcheck 失敗：%s", e)
            return False
    return True


@asynccontextmanager
async def get_conn() -> AsyncIterator[AsyncConnection]:
    """以 context manager 形式取出共享連線。供 FastAPI dependency 使用。"""
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    yield _conn  # type: ignore[misc]


async def require_tech_conn() -> AsyncConnection:
    """技師域連線（CR-0112 方案 B）：雙庫模式回技師庫，否則回主連線（fallback）。

    非 context-manager 風格，供既有「先 ensure 再用模組連線」的 service 慣例改造用。
    """
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            raise RuntimeError("Tech DB unavailable")
        return _tech_conn  # type: ignore[return-value]
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    return _conn  # type: ignore[return-value]


@asynccontextmanager
async def get_tech_conn() -> AsyncIterator[AsyncConnection]:
    """技師域連線的 context-manager 形式（未配置技師庫時 fallback 主連線）。"""
    yield await require_tech_conn()


async def require_platform_conn() -> AsyncConnection:
    """平台域連線（CR-0114）：配置平台庫時回平台庫，否則回主連線（fallback）。

    與 require_tech_conn 同款安全閥：PLATFORM_POSTGRES_URI 未設（pytest/CI/
    單庫部署）時行為與主連線完全相同。
    """
    if platform_db_enabled():
        if not await _ensure_platform_conn():
            raise RuntimeError("Platform DB unavailable")
        return _platform_conn  # type: ignore[return-value]
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    return _conn  # type: ignore[return-value]


@asynccontextmanager
async def get_platform_conn() -> AsyncIterator[AsyncConnection]:
    """平台域連線的 context-manager 形式（未配置平台庫時 fallback 主連線）。"""
    yield await require_platform_conn()
