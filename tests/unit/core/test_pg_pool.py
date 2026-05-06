"""Unit tests for `agent/core/pg_pool.py` — shared async PG connection helper.

We mock `psycopg.AsyncConnection.connect` so the tests don't require a live DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset module-level cache before *every* test to avoid cross-test bleed."""
    from core.pg_pool import _CONN_CACHE

    _CONN_CACHE.clear()
    yield
    _CONN_CACHE.clear()


def _make_conn(*, closed: bool = False, broken: bool = False) -> MagicMock:
    """Build a fake AsyncConnection mock with closeable async lifecycle."""
    conn = MagicMock(name="AsyncConnection")
    conn.closed = closed
    conn.broken = broken
    conn.close = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_get_async_conn_creates_new_when_cache_empty():
    """First call for a name should establish a fresh connection."""
    from core import pg_pool

    fresh = _make_conn()
    with patch(
        "psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=fresh),
    ) as connect_mock:
        result = await pg_pool.get_async_conn("test", "postgresql://x")

    assert result is fresh
    connect_mock.assert_awaited_once_with("postgresql://x", autocommit=True)
    assert pg_pool._CONN_CACHE["test"] is fresh


@pytest.mark.asyncio
async def test_get_async_conn_returns_cached_when_alive():
    """Second call for an alive cached conn must NOT reconnect."""
    from core import pg_pool

    cached = _make_conn()
    pg_pool._CONN_CACHE["alive"] = cached

    with patch(
        "psycopg.AsyncConnection.connect", new=AsyncMock()
    ) as connect_mock:
        result = await pg_pool.get_async_conn("alive", "postgresql://x")

    assert result is cached
    connect_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_async_conn_reconnects_when_closed():
    """A closed cached conn must be replaced and old one closed."""
    from core import pg_pool

    stale = _make_conn(closed=True)
    pg_pool._CONN_CACHE["stale"] = stale

    fresh = _make_conn()
    with patch(
        "psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=fresh),
    ) as connect_mock:
        result = await pg_pool.get_async_conn("stale", "postgresql://x")

    assert result is fresh
    connect_mock.assert_awaited_once_with("postgresql://x", autocommit=True)
    stale.close.assert_awaited_once()
    assert pg_pool._CONN_CACHE["stale"] is fresh


@pytest.mark.asyncio
async def test_get_async_conn_reconnects_when_broken():
    """A broken cached conn (CloudSQL idle disconnect) must be replaced."""
    from core import pg_pool

    broken_conn = _make_conn(broken=True)
    pg_pool._CONN_CACHE["broken"] = broken_conn

    fresh = _make_conn()
    with patch(
        "psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=fresh),
    ):
        result = await pg_pool.get_async_conn("broken", "postgresql://x")

    assert result is fresh
    broken_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_async_conn_swallows_close_errors_on_replace():
    """If old conn.close() raises, we still replace and return the new one."""
    from core import pg_pool

    stale = _make_conn(closed=True)
    stale.close = AsyncMock(side_effect=RuntimeError("close failed"))
    pg_pool._CONN_CACHE["err"] = stale

    fresh = _make_conn()
    with patch(
        "psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=fresh),
    ):
        result = await pg_pool.get_async_conn("err", "postgresql://x")

    assert result is fresh
    assert pg_pool._CONN_CACHE["err"] is fresh


@pytest.mark.asyncio
async def test_get_cached_returns_none_when_absent():
    from core import pg_pool

    assert pg_pool.get_cached("missing") is None


@pytest.mark.asyncio
async def test_set_cached_replaces_and_clears():
    from core import pg_pool

    conn = _make_conn()
    pg_pool.set_cached("k", conn)
    assert pg_pool.get_cached("k") is conn

    pg_pool.set_cached("k", None)
    assert pg_pool.get_cached("k") is None
    assert "k" not in pg_pool._CONN_CACHE


@pytest.mark.asyncio
async def test_close_all_closes_every_cached_conn():
    from core import pg_pool

    a = _make_conn()
    b = _make_conn()
    pg_pool._CONN_CACHE["a"] = a
    pg_pool._CONN_CACHE["b"] = b

    await pg_pool.close_all()

    a.close.assert_awaited_once()
    b.close.assert_awaited_once()
    assert pg_pool._CONN_CACHE == {}


@pytest.mark.asyncio
async def test_close_all_swallows_close_exceptions():
    """One bad close must not block the others or leave cache populated."""
    from core import pg_pool

    bad = _make_conn()
    bad.close = AsyncMock(side_effect=RuntimeError("boom"))
    good = _make_conn()
    pg_pool._CONN_CACHE["bad"] = bad
    pg_pool._CONN_CACHE["good"] = good

    await pg_pool.close_all()

    good.close.assert_awaited_once()
    assert pg_pool._CONN_CACHE == {}
