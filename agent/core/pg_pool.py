"""Shared PostgreSQL async connection helper with auto-reconnect.

CloudSQL idle timeout (typically 10 min) silently closes connections.
This helper centralises the reconnect logic that previously lived in
three near-identical `_ensure_conn` implementations across:

    - profiles/manager.py        (facts DB)
    - storage/postgres_impl.py   (audit DB)
    - harness/data_correction.py (data correction DB)

memory/postgres_saver.py is intentionally *not* wired into this pool
because the connection there is owned by the LangGraph
`AsyncPostgresSaver` and uses non-default kwargs
(`prepare_threshold=0`, `row_factory=dict_row`); sharing through this
cache would break the saver's lifecycle assumptions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import AsyncConnection

logger = logging.getLogger(__name__)

# Per-name connection cache (e.g. "facts", "audit", "data_correction")
_CONN_CACHE: dict[str, "AsyncConnection"] = {}


def _is_alive(conn: "AsyncConnection | None") -> bool:
    """Return True iff conn exists and is neither closed nor broken."""
    if conn is None:
        return False
    if conn.closed:
        return False
    # `broken` exists on psycopg3 AsyncConnection — guard for safety.
    broken = getattr(conn, "broken", False)
    return not broken


async def get_async_conn(name: str, uri: str) -> "AsyncConnection":
    """Idempotent fetcher of an autocommit AsyncConnection.

    - Returns cached connection if alive (`closed=False` and `broken=False`).
    - Reconnects transparently on CloudSQL idle disconnect / server restart.
    - Always uses `autocommit=True` to match existing modules' contract.

    Raises:
        Any psycopg connection exception. Callers should catch and downgrade
        to a "feature disabled" mode if their failure semantics demand it.
    """
    from psycopg import AsyncConnection

    cached = _CONN_CACHE.get(name)
    if _is_alive(cached):
        return cached  # type: ignore[return-value]

    if cached is not None:
        # Old connection went stale — close it best-effort before replacing.
        logger.warning("pg_pool: reconnecting %s (previous conn closed/broken)", name)
        try:
            await cached.close()
        except Exception as e:  # noqa: BLE001 — best-effort cleanup
            logger.warning(
                "pg_pool: close stale conn %s failed: %s", name, e, exc_info=True
            )

    # pg_pool helper owns connection lifecycle on behalf of callers; the lint
    # rule (DB connection pattern lint) targets ad-hoc connect() in feature code.
    new_conn = await AsyncConnection.connect(uri, autocommit=True)  # allow-direct-conn
    _CONN_CACHE[name] = new_conn
    return new_conn


def get_cached(name: str) -> "AsyncConnection | None":
    """Return the cached connection without reconnecting (for health checks)."""
    return _CONN_CACHE.get(name)


def set_cached(name: str, conn: "AsyncConnection | None") -> None:
    """Replace or clear a cached connection (used by init/close lifecycle)."""
    if conn is None:
        _CONN_CACHE.pop(name, None)
    else:
        _CONN_CACHE[name] = conn


async def close_all() -> None:
    """Close every cached connection (e.g. on application shutdown)."""
    for name, conn in list(_CONN_CACHE.items()):
        try:
            await conn.close()
        except Exception as e:  # noqa: BLE001 — best-effort cleanup
            logger.warning("pg_pool: close %s failed: %s", name, e, exc_info=True)
    _CONN_CACHE.clear()
