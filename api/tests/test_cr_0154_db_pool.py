"""CR-0154:request-scoped 連線池(ADR-006 Phase 1/業主裁決選項 A)。

驗證面:①模組屬性攔截(直接賦值導回共享槽、scoped 優先);②池啟用時並發
scope 各持不同連線(解 app 端序列化);③scope 內交易+FOR UPDATE 同連線語意;
④kill-switch 降級;⑤池未啟用 middleware 直通(既有行為)。
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component


def test_property_interception_sync():
    """直接賦值 → 共享槽;scoped 設定時讀取優先(不需 DB)。"""
    original = db_module._shared_conn
    try:
        db_module._conn = "fake-shared"
        assert db_module._shared_conn == "fake-shared"
        tok = db_module._scoped_conn.set("scoped")
        assert db_module._conn == "scoped"
        db_module._scoped_conn.reset(tok)
        assert db_module._conn == "fake-shared"
    finally:
        db_module._conn = original


@pytest.mark.asyncio
async def test_pool_scope_concurrent_distinct_conns(monkeypatch):
    """池啟用:兩個並發 scope 各持不同池連線且都可查詢。"""
    monkeypatch.delenv("DB_POOL_DISABLED", raising=False)
    assert await db_module.open_pool(), "scratch 庫應可開池"
    try:
        seen: list[object] = []

        async def probe():
            async with db_module.pool_scope():
                conn = db_module._conn
                seen.append(conn)
                cur = await conn.execute("SELECT 1")
                assert (await cur.fetchone())[0] == 1
                await asyncio.sleep(0.05)  # 重疊窗口,逼兩 task 各借一條

        await asyncio.gather(probe(), probe())
        assert len(seen) == 2 and seen[0] is not seen[1], "並發 scope 應各持連線"
    finally:
        await db_module.close_pool()


@pytest.mark.asyncio
async def test_transaction_for_update_within_scope(monkeypatch):
    """scope 內 async with _conn.transaction()+FOR UPDATE:同 task 同連線,
    交易語意保留(CR-0154 選項 A 的核心保證)。"""
    monkeypatch.delenv("DB_POOL_DISABLED", raising=False)
    assert await db_module.open_pool()
    pid = str(uuid.uuid4())
    try:
        async with db_module.pool_scope():
            conn = db_module._conn
            await conn.execute(
                "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
                "VALUES (%s::uuid, '00000000-0000-0000-0000-000000000001', "
                "'Chatlock', 'A90', 'draft')", (pid,))
            async with conn.transaction():
                # 交易中的每個語句都經 db_module._conn 解析 → 必須同一條連線
                assert db_module._conn is conn
                cur = await db_module._conn.execute(
                    "SELECT id FROM problem_cards WHERE id=%s::uuid FOR UPDATE", (pid,))
                assert (await cur.fetchone()) is not None
                await db_module._conn.execute(
                    "UPDATE problem_cards SET status='confirmed' WHERE id=%s::uuid", (pid,))
            cur = await conn.execute(
                "SELECT status FROM problem_cards WHERE id=%s::uuid", (pid,))
            assert (await cur.fetchone())[0] == "confirmed"
    finally:
        async with db_module.pool_scope():
            await db_module._conn.execute(
                "DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
        await db_module.close_pool()


@pytest.mark.asyncio
async def test_kill_switch_disables_pool(monkeypatch):
    monkeypatch.setenv("DB_POOL_DISABLED", "1")
    assert await db_module.open_pool() is False
    assert not db_module.pool_enabled()
    # scope 無作用:_conn 解析回共享連線(既有語意)
    assert await db_module._ensure_conn()
    shared = db_module._shared_conn
    async with db_module.pool_scope():
        assert db_module._conn is shared


@pytest.mark.asyncio
async def test_middleware_passthrough_when_pool_off(client, admin_headers):
    """池未啟用(測試預設):middleware 直通,既有請求路徑不變。"""
    assert not db_module.pool_enabled()
    r = await client.get("/health")
    assert r.status_code == 200
