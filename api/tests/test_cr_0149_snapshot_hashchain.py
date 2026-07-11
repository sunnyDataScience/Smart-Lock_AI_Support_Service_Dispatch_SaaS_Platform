"""CR-0149:ADR-026 content-addressable 報價快照(migration 098)。

send 凍結 → 新表 sha256 定址+quote.snapshot_hash reference pointer;
同 payload 去重(insert 冪等);append-only trigger 擋 UPDATE/DELETE(owner 亦擋);
舊制表更名 pricing_rule_snapshot_legacy 保留。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"


async def _mk_quote_with_lines(*, price: float = 800.0) -> tuple[str, str, str]:
    """WO+draft quote+一條 line;回 (wid, pid, qid)。"""
    assert await db_module._ensure_conn()
    wid, pid, qid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, customer_address, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'in_progress', %s::uuid, '台北市測試路1號', %s::uuid)",
        (wid, pid, SEED_TECH, TID))
    await db_module._conn.execute(
        "INSERT INTO quote (id, tenant_id, problem_card_id, work_order_id, state, version, total_amount) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'draft', 1, %s)",
        (qid, TID, pid, wid, price))
    await db_module._conn.execute(
        "INSERT INTO quote_line_items (id, work_order_id, tenant_id, quote_id, item_name, category, "
        "unit_price, quantity, customer_price, is_mock) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, '鎖芯更換', 'service', %s, 1, %s, FALSE)",
        (str(uuid.uuid4()), wid, TID, qid, price, price))
    return wid, pid, qid


async def _cleanup(wid: str, pid: str) -> None:
    if not await db_module._ensure_conn():
        return
    # 快照表 append-only(098),不清——content-addressable 行可跨測試共享
    await db_module._conn.execute("DELETE FROM quote_line_items WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))


async def _send(client, headers, qid: str) -> dict:
    r = await client.post(
        f"/tenants/{TID}/quotes/{qid}:send",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_send_freezes_content_addressable_snapshot(client, secondary_admin_headers):
    wid, pid, qid = await _mk_quote_with_lines()
    try:
        await _send(client, secondary_admin_headers, qid)
        row = await (await db_module._conn.execute(
            "SELECT q.snapshot_hash, s.engine_type, s.tenant_id::text, "
            "s.payload->'lines'->0->>'name', s.payload->>'tenant_id' "
            "FROM quote q JOIN pricing_rule_snapshot s ON s.snapshot_hash = q.snapshot_hash "
            "WHERE q.id = %s::uuid", (qid,))).fetchone()
        assert row is not None, "send 後 quote.snapshot_hash 應指向快照行"
        h, engine, s_tid, first_line, payload_tid = row
        assert len(h) == 64 and engine == "quote_line_items_v1"
        assert s_tid == TID and payload_tid == TID  # tenant 入 payload=去重範圍租戶內
        assert first_line == "鎖芯更換"
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_dedup_same_payload_single_row(client, secondary_admin_headers):
    """同 payload(同 lines+policy)兩次 send → 同 hash、快照表僅一行(冪等去重)。"""
    w1, p1, q1 = await _mk_quote_with_lines(price=1234.0)
    w2, p2, q2 = await _mk_quote_with_lines(price=1234.0)
    try:
        await _send(client, secondary_admin_headers, q1)
        await _send(client, secondary_admin_headers, q2)
        rows = await (await db_module._conn.execute(
            "SELECT DISTINCT snapshot_hash FROM quote WHERE id IN (%s::uuid, %s::uuid)",
            (q1, q2))).fetchall()
        assert len(rows) == 1, "同 payload 應得同 hash"
        cnt = await (await db_module._conn.execute(
            "SELECT count(*) FROM pricing_rule_snapshot WHERE snapshot_hash = %s",
            (rows[0][0],))).fetchone()
        assert cnt[0] == 1, "content-addressable 去重:同 hash 僅一行"
    finally:
        await _cleanup(w1, p1)
        await _cleanup(w2, p2)


@pytest.mark.asyncio
async def test_append_only_trigger_blocks_update_delete(client, secondary_admin_headers):
    wid, pid, qid = await _mk_quote_with_lines(price=555.0)
    try:
        await _send(client, secondary_admin_headers, qid)
        h = (await (await db_module._conn.execute(
            "SELECT snapshot_hash FROM quote WHERE id = %s::uuid", (qid,))).fetchone())[0]

        import psycopg

        with pytest.raises(psycopg.errors.RaiseException):
            await db_module._conn.execute(
                "UPDATE pricing_rule_snapshot SET engine_type='tampered' WHERE snapshot_hash=%s", (h,))
        with pytest.raises(psycopg.errors.RaiseException):
            await db_module._conn.execute(
                "DELETE FROM pricing_rule_snapshot WHERE snapshot_hash=%s", (h,))
        # 行仍在且未被竄改(autocommit 連線,失敗語句不汙染後續)
        row = await (await db_module._conn.execute(
            "SELECT engine_type FROM pricing_rule_snapshot WHERE snapshot_hash=%s", (h,))).fetchone()
        assert row[0] == "quote_line_items_v1"
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_legacy_table_preserved():
    assert await db_module._ensure_conn()
    row = await (await db_module._conn.execute(
        "SELECT to_regclass('public.pricing_rule_snapshot_legacy') IS NOT NULL")).fetchone()
    assert row[0] is True, "舊制表應更名保留(業主裁決:查證用)"
