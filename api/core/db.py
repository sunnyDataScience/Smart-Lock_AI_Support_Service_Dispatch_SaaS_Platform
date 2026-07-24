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
import sys
import types
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator

from psycopg import AsyncConnection

logger = logging.getLogger("api.db")

_shared_conn: AsyncConnection | None = None
_uri_env: str = "POSTGRES_URI"

_tech_conn: AsyncConnection | None = None
_TECH_URI_ENV: str = "TECH_POSTGRES_URI"

_platform_conn: AsyncConnection | None = None
_PLATFORM_URI_ENV: str = "PLATFORM_POSTGRES_URI"


async def _ensure_conn() -> bool:
    global _shared_conn
    # getattr 防禦:單元測試以假連線(無 closed/broken 屬性)monkeypatch _conn,
    # 視為健康直接沿用(真 psycopg 連線兩屬性必存在)。
    if _shared_conn is not None and not getattr(_shared_conn, "closed", False) and not getattr(_shared_conn, "broken", False):
        return True
    uri = os.getenv(_uri_env)
    if not uri:
        logger.error("環境變數 %s 未設定", _uri_env)
        return False
    try:
        if _shared_conn is not None:
            try:
                await _shared_conn.close()
            except Exception as e:
                logger.warning("[DB] close 既有連線失敗（將以新連線取代）: %s", e, exc_info=True)
        _shared_conn = await AsyncConnection.connect(uri, autocommit=True)
        logger.info("[DB] 已連線（autocommit=True, env=%s）", _uri_env)
        return True
    except Exception as e:
        logger.error("[DB] 連線失敗：%s", e)
        _shared_conn = None
        return False


def assert_uri_strict() -> None:
    """三庫 URI 啟動守衛(ADR-020 Consequences/CR-0153,opt-in)。

    `DB_URI_STRICT=1` 時依 API_SURFACE 斷言該面必要的庫 URI 已配置——
    漏設直接 RuntimeError 拒啟,不得靜默 fallback 單庫(prod 三庫部署防
    「以為在打技師庫其實寫進品牌庫」)。預設關閉:本機/pytest 單庫
    fallback 行為完全不變。
    """
    if os.getenv("DB_URI_STRICT", "").strip() != "1":
        return
    surface = os.getenv("API_SURFACE", "all").strip().lower() or "all"
    missing: list[str] = []
    if not os.getenv(_uri_env):
        missing.append(_uri_env)
    if surface == "tech" and not os.getenv(_TECH_URI_ENV):
        missing.append(_TECH_URI_ENV)
    if surface == "platform":
        if not os.getenv(_PLATFORM_URI_ENV):
            missing.append(_PLATFORM_URI_ENV)
        # 0724 split-brain 實案：平台面是技師生命週期操作面（onboard-approve/
        # 停權/終止寫技師權威庫）。漏掛 TECH_POSTGRES_URI 時 require_tech_conn
        # fallback 主庫 → 核准寫進投影、權威庫仍 pending，平台頁顯示啟用中
        # 但技師登入被拒（ACCOUNT_PENDING_APPROVAL）。依 ADR-020 fail-fast。
        if not os.getenv(_TECH_URI_ENV):
            missing.append(_TECH_URI_ENV)
    if missing:
        raise RuntimeError(
            f"DB_URI_STRICT=1 拒絕啟動(API_SURFACE={surface}):缺 {', '.join(missing)}"
            "——三庫部署禁止靜默 fallback 單庫(ADR-020)"
        )


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
    global _shared_conn, _tech_conn, _platform_conn
    await close_pool()
    if _shared_conn is not None:
        try:
            await _shared_conn.close()
        finally:
            _shared_conn = None
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
        cur = await _shared_conn.execute("SELECT 1")
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
    scoped = _scoped_conn.get()
    if scoped is not None:
        yield scoped
        return
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    yield _shared_conn  # type: ignore[misc]


_tech_fallback_warned = False


async def require_tech_conn() -> AsyncConnection:
    """技師域連線（CR-0112 方案 B）：雙庫模式回技師庫，否則回主連線（fallback）。

    非 context-manager 風格，供既有「先 ensure 再用模組連線」的 service 慣例改造用。
    """
    global _tech_fallback_warned
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            raise RuntimeError("Tech DB unavailable")
        return _tech_conn  # type: ignore[return-value]
    # UAT R3-2 設計半部：fail-soft 不再靜默——首次 fallback 即 WARNING。
    # （行為不變：單庫部署/pytest 仍照常回主連線；雙庫部署漏帶 env 至少留下線索）
    if not _tech_fallback_warned:
        _tech_fallback_warned = True
        logger.warning(
            "TECH_POSTGRES_URI 未設，技師權威庫讀寫 fallback 品牌庫——"
            "雙庫部署漏此 env 會 split-brain（排班申請/技師身分寫錯庫，UAT R3-2）；"
            "單庫部署可忽略本警告"
        )
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    return _current_conn()  # type: ignore[return-value]


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
    return _current_conn()  # type: ignore[return-value]


@asynccontextmanager
async def get_platform_conn() -> AsyncIterator[AsyncConnection]:
    """平台域連線的 context-manager 形式（未配置平台庫時 fallback 主連線）。"""
    yield await require_platform_conn()


# ── CR-0154（ADR-006 Phase 1／業主 2026-07-10 裁決選項 A）──────────────────
# request-scoped 連線池：http 請求各借一條池連線入 ContextVar，`db_module._conn`
# 一律「scoped 優先、共享 fallback」解析——660 個既有呼叫點零改動、同 task 內
# 交易（async with _conn.transaction() / FOR UPDATE）天然同連線。共享連線保留
# 給 cron worker／WS／池未啟用情境（=改造前語意）。kill-switch：DB_POOL_DISABLED=1。

_scoped_conn: ContextVar[AsyncConnection | None] = ContextVar(
    "db_scoped_conn", default=None
)
_pool: Any = None  # psycopg_pool.AsyncConnectionPool | None（lazy import）


def _current_conn() -> AsyncConnection | None:
    scoped = _scoped_conn.get()
    return scoped if scoped is not None else _shared_conn


def pool_enabled() -> bool:
    return _pool is not None


async def open_pool() -> bool:
    """lifespan 開池。DB_POOL_DISABLED=1／URI 缺／psycopg_pool 缺／開池失敗
    一律降級共享連線（絕不癱瘓啟動）。"""
    global _pool
    if _pool is not None:
        return True
    if os.getenv("DB_POOL_DISABLED", "").strip() == "1":
        logger.info("[DBPool] DB_POOL_DISABLED=1 → 停用（共享連線 fallback）")
        return False
    uri = os.getenv(_uri_env)
    if not uri:
        return False
    try:
        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(
            uri,
            min_size=int(os.getenv("DB_POOL_MIN", "1")),
            max_size=int(os.getenv("DB_POOL_MAX", "10")),
            kwargs={"autocommit": True},
            open=False,
        )
        await pool.open(wait=True, timeout=30)
        _pool = pool
        logger.info(
            "[DBPool] 連線池已開（min=%s, max=%s）", pool.min_size, pool.max_size
        )
        return True
    except Exception as e:  # noqa: BLE001 — 池失敗不可癱瘓服務
        logger.error("[DBPool] 開池失敗（fallback 共享連線）：%s", e)
        _pool = None
        return False


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[DBPool] close 失敗（略過）：%s", e)
        finally:
            _pool = None


@asynccontextmanager
async def pool_scope() -> AsyncIterator[None]:
    """借一條池連線入 ContextVar；離開歸還。池未啟用＝無作用（fallback）。"""
    if _pool is None:
        yield
        return
    async with _pool.connection() as conn:
        token = _scoped_conn.set(conn)
        try:
            yield
        finally:
            _scoped_conn.reset(token)


class DBPoolScopeMiddleware:
    """純 ASGI：http 請求包 pool_scope。websocket 不包（長連線佔池；WS 面
    維持共享連線＝既有語意）；池未啟用時零開銷直通。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or _pool is None:
            await self.app(scope, receive, send)
            return
        async with pool_scope():
            await self.app(scope, receive, send)


class _DbModule(types.ModuleType):
    """模組屬性攔截（CR-0154）：`db_module._conn` 讀＝scoped 優先；寫＝導回
    共享槽——既有測試「直接賦值 FakeConn」慣例（conftest _isolate_db_conn 亦
    直接賦值 None）因此零破壞，不會遮蔽 property。"""

    @property
    def _conn(self) -> AsyncConnection | None:  # type: ignore[override]
        return _current_conn()

    @_conn.setter
    def _conn(self, value: AsyncConnection | None) -> None:
        global _shared_conn
        _shared_conn = value


sys.modules[__name__].__class__ = _DbModule
