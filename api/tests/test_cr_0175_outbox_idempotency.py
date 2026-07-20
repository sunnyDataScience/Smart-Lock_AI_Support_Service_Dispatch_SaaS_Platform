"""CR-0175 — outbox enqueue 冪等 unit tests(conn mocked,無需 DB)。

驗證 R13 去重分支邏輯：
- strict push_kind(事件型)+ reference_id → 走 ON CONFLICT DO NOTHING；撞既有回既有 id。
- 可更新型 kind / 無 reference_id → 維持無條件 INSERT(允許合法重推)。

(DB 層 partial unique index 真實行為由 migration 111 + 真 DB 整合測試涵蓋;
 本檔以 FakeConn 驗 Python 控制流與 SQL 形狀,對齊 conftest 既有 mock 慣例。)
"""

from __future__ import annotations

import pytest

import core.db as dbm
import services.line_push_outbox_service as svc

_TENANT = "00000000-0000-0000-0000-000000000001"


class _FakeCur:
    def __init__(self, one):
        self._one = one

    async def fetchone(self):
        return self._one


class _FakeConn:
    """依 SQL 前綴回傳既定 row;記錄所有 execute 的 SQL 供斷言。"""

    def __init__(self, *, insert_returns, select_returns=None):
        self.sqls: list[str] = []
        self._insert_returns = insert_returns
        self._select_returns = select_returns

    async def execute(self, sql, params=None):
        self.sqls.append(sql)
        s = sql.strip()
        if s.startswith("INSERT"):
            return _FakeCur(self._insert_returns)
        if s.startswith("SELECT"):
            return _FakeCur(self._select_returns)
        return _FakeCur(None)


async def _true():
    return True


@pytest.fixture
def wire(monkeypatch):
    """安裝 fake conn + _ensure_conn=True。"""
    def install(fake):
        monkeypatch.setattr(svc, "_ensure_conn", _true)
        monkeypatch.setattr(dbm, "_conn", fake)
        return fake
    return install


@pytest.mark.asyncio
async def test_enqueue_strict_conflict_returns_existing_id(wire):
    """strict kind 撞既有(ON CONFLICT DO NOTHING → 無 RETURNING)→ 回既有 id,不重複推。"""
    fake = wire(_FakeConn(insert_returns=None, select_returns=("existing-id",)))
    oid = await svc.enqueue(
        tenant_id=_TENANT, push_kind="work_order_assigned", payload={"a": 1},
        reference_id="11111111-1111-1111-1111-111111111111",
        reference_table="work_orders",
    )
    assert oid == "existing-id"
    assert any("ON CONFLICT" in s for s in fake.sqls)               # 走去重路徑
    assert any(s.strip().startswith("SELECT") for s in fake.sqls)   # 冪等回既有


@pytest.mark.asyncio
async def test_enqueue_strict_no_conflict_returns_new_id(wire):
    """strict kind 無衝突 → 正常回新 id,不需 fallback SELECT。"""
    fake = wire(_FakeConn(insert_returns=("new-id",)))
    oid = await svc.enqueue(
        tenant_id=_TENANT, push_kind="work_order_document", payload={"a": 1},
        reference_id="22222222-2222-2222-2222-222222222222",
        reference_table="work_orders",
    )
    assert oid == "new-id"
    assert any("ON CONFLICT" in s for s in fake.sqls)
    assert not any(s.strip().startswith("SELECT") for s in fake.sqls)


@pytest.mark.asyncio
async def test_enqueue_repushable_kind_no_dedup(wire):
    """可更新型 kind(quote_proposal)維持無條件 INSERT,不走 ON CONFLICT(允許合法重推)。"""
    fake = wire(_FakeConn(insert_returns=("new-id-2",)))
    oid = await svc.enqueue(
        tenant_id=_TENANT, push_kind="quote_proposal", payload={"a": 1},
        reference_id="33333333-3333-3333-3333-333333333333",
        reference_table="quotes",
    )
    assert oid == "new-id-2"
    assert not any("ON CONFLICT" in s for s in fake.sqls)


@pytest.mark.asyncio
async def test_enqueue_strict_without_reference_id_no_dedup(wire):
    """strict kind 但無 reference_id → 無從去重,維持無條件 INSERT。"""
    fake = wire(_FakeConn(insert_returns=("nid",)))
    oid = await svc.enqueue(
        tenant_id=_TENANT, push_kind="work_order_assigned", payload={"a": 1},
        reference_id=None,
    )
    assert oid == "nid"
    assert not any("ON CONFLICT" in s for s in fake.sqls)
