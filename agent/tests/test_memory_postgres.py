"""CR-0023 / ADR-0113：agent 記憶 Postgres 後端測試。

- SQLite 與 Postgres 兩後端**同介面同行為**(scope 隔離 / 中文子字串檢索 / forget)。
- Postgres 測試需真實 DB:設環境變數 `POSTGRES_URI`(且已跑 SQL/migrations/033)才執行,
  否則整段 skip(本機快速 unit run 不被阻擋)。

跑法:
    cd agent && pip install -e ".[dev,postgres]"
    POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data" pytest tests/test_memory_postgres.py
"""

from __future__ import annotations

import os
import uuid

import pytest

from lockcore.agent.user_memory import SqliteMemoryProvider

T = "locksmart"

_PG_URI = os.getenv("POSTGRES_URI")
requires_pg = pytest.mark.skipif(not _PG_URI, reason="POSTGRES_URI 未設,跳過 Postgres 後端測試")


def _new_user() -> str:
    return "U" + uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# SQLite 後端(無需 DB,作為兩後端行為的基準)
# ---------------------------------------------------------------------------


def test_sqlite_scope_isolation_and_search():
    p = SqliteMemoryProvider(":memory:")
    u1, u2 = _new_user(), _new_user()
    p.store.add(T, u1, "fact", "客人的鎖是 Dormakaba AS701")
    p.store.add(T, u2, "fact", "別人的鎖 Gateman G100")
    # 中文子字串檢索命中
    assert [e.content for e in p.store.search(T, u1, "AS701")] == ["客人的鎖是 Dormakaba AS701"]
    # scope 隔離:u1 看不到 u2
    assert len(p.store.list_for_user(T, u1)) == 1


def test_sqlite_default_deny():
    p = SqliteMemoryProvider(":memory:")
    with pytest.raises(ValueError):
        p.store.add(T, "", "fact", "x")


# ---------------------------------------------------------------------------
# Postgres 後端(需 POSTGRES_URI + migration 033)
# ---------------------------------------------------------------------------


@pytest.fixture()
def pg_provider():
    from lockcore.agent.user_memory.provider import PostgresMemoryProvider

    p = PostgresMemoryProvider(_PG_URI)
    user = _new_user()
    yield p, user
    p.forget(T, user)  # 測試後清乾淨
    p.store.close()


@requires_pg
def test_pg_search_chinese_substring(pg_provider):
    p, u = pg_provider
    p.store.add(T, u, "fact", "客人的鎖是 Dormakaba AS701")
    p.store.add(T, u, "preference", "偏好下午到府")
    # pg_trgm ILIKE 子字串
    assert [e.content for e in p.store.search(T, u, "AS701")] == ["客人的鎖是 Dormakaba AS701"]
    assert len(p.store.search(T, u, "鎖")) == 1


@requires_pg
def test_pg_scope_isolation_and_forget(pg_provider):
    p, u = pg_provider
    other = _new_user()
    p.store.add(T, u, "fact", "我的鎖")
    p.store.add(T, other, "fact", "別人的鎖")
    try:
        assert len(p.store.list_for_user(T, u)) == 1  # 看不到 other
        removed = p.forget(T, u)
        assert removed == 1
        assert p.store.list_for_user(T, u) == []
    finally:
        p.forget(T, other)


@requires_pg
def test_pg_default_deny(pg_provider):
    p, _ = pg_provider
    with pytest.raises(ValueError):
        p.store.add(T, "", "fact", "x")


@requires_pg
def test_pg_escalation_roundtrip():
    from lockcore.agent.user_memory.postgres_store import PostgresEscalationStore

    esc = PostgresEscalationStore(_PG_URI)
    u = _new_user()
    esc.log(T, u, "客人要求轉真人", True, {"brand": "Dormakaba", "model": "AS701"})
    recs = esc.list_for_user(T, u)
    assert len(recs) == 1
    assert recs[0].is_explicit is True
    assert recs[0].facts_snapshot["model"] == "AS701"
    esc.close()


@requires_pg
def test_app_config_backend_switch():
    """build_memory_manager / build_escalation_store 依 backend 切換正確 provider。"""
    import dataclasses

    from lockcore.app_config import build_escalation_store, build_memory_manager, load_config

    cfg = dataclasses.replace(load_config(), backend="postgres", extractor="raw")
    mgr = build_memory_manager(cfg, provider=None)
    assert type(mgr.provider).__name__ == "PostgresMemoryProvider"
    assert type(build_escalation_store(cfg)).__name__ == "PostgresEscalationStore"

    cfg_sq = dataclasses.replace(load_config(), backend="sqlite", db_path=":memory:", extractor="raw")
    assert type(build_memory_manager(cfg_sq).provider).__name__ == "SqliteMemoryProvider"
