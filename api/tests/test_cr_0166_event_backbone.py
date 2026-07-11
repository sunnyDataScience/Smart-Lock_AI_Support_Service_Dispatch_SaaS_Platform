"""CR-0166 R4：Kafka/Redpanda 事件骨幹——producer no-op、consumer 投影 handler、對帳閘門。

不需真 broker：event_bus 未設 KAFKA_BOOTSTRAP → no-op；consumer handler 為純邏輯（吃 conn），
對 scratch DB 驗證投影 upsert＋冪等＋reconcile。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import event_reconcile_service as recon
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"


# ── producer no-op（未設 KAFKA_BOOTSTRAP）─────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_noop_when_disabled(monkeypatch):
    from core import event_bus
    monkeypatch.delenv("KAFKA_BOOTSTRAP", raising=False)
    assert event_bus.enabled() is False
    ok = await event_bus.publish_event("workorder.lifecycle", {"work_order_id": "x"})
    assert ok is False  # no-op，不 raise


# ── consumer 投影 handler（scratch DB）───────────────────────────────────────

async def _cleanup_proj(wo_id=None, sid=None, eid=None) -> None:
    await db_module._ensure_conn()
    if wo_id:
        await db_module._conn.execute(
            "DELETE FROM technician_workorder_projection WHERE work_order_id=%s::uuid", (wo_id,))
    if sid:
        await db_module._conn.execute(
            "DELETE FROM technician_commission_projection WHERE settlement_id=%s::uuid", (sid,))
    if eid:
        await db_module._conn.execute("DELETE FROM event_consumer_dedup WHERE event_id=%s", (eid,))


@pytest.mark.asyncio
async def test_workorder_projection_upsert():
    from realtime import event_consumer
    wo_id = str(uuid.uuid4())
    eid = str(uuid.uuid4())
    try:
        ok = await event_consumer.process_event("workorder.lifecycle", {
            "event_id": eid, "work_order_id": wo_id, "tenant_id": TID,
            "technician_id": SEED_TECH, "status": "assigned",
            "document_number": "TP-000123", "district": "台北市信義區",
            "event_type": "work_order.assigned",
        })
        assert ok is True
        row = await (await db_module._conn.execute(
            "SELECT status, technician_id::text, district, last_event_type "
            "FROM technician_workorder_projection WHERE work_order_id=%s::uuid", (wo_id,))).fetchone()
        assert row[0] == "assigned" and row[1] == SEED_TECH
        assert row[2] == "台北市信義區" and row[3] == "work_order.assigned"

        # 冪等：同 event_id 再處理 → False（skip），不改投影
        ok2 = await event_consumer.process_event("workorder.lifecycle", {
            "event_id": eid, "work_order_id": wo_id, "tenant_id": TID,
            "status": "completed",  # 不同 status，但同 event_id → 應被去重
        })
        assert ok2 is False
        st = await (await db_module._conn.execute(
            "SELECT status FROM technician_workorder_projection WHERE work_order_id=%s::uuid", (wo_id,))).fetchone()
        assert st[0] == "assigned"  # 未被重複事件改動
    finally:
        await _cleanup_proj(wo_id=wo_id, eid=eid)


@pytest.mark.asyncio
async def test_workorder_projection_status_progression():
    """不同 event_id 的後續事件 → 投影更新（狀態推進）。"""
    from realtime import event_consumer
    wo_id = str(uuid.uuid4())
    e1, e2 = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        await event_consumer.process_event("workorder.lifecycle", {
            "event_id": e1, "work_order_id": wo_id, "tenant_id": TID,
            "technician_id": SEED_TECH, "status": "assigned"})
        await event_consumer.process_event("workorder.lifecycle", {
            "event_id": e2, "work_order_id": wo_id, "tenant_id": TID,
            "technician_id": SEED_TECH, "status": "accepted"})
        st = await (await db_module._conn.execute(
            "SELECT status FROM technician_workorder_projection WHERE work_order_id=%s::uuid", (wo_id,))).fetchone()
        assert st[0] == "accepted"
    finally:
        await _cleanup_proj(wo_id=wo_id, eid=e1)
        await _cleanup_proj(eid=e2)


@pytest.mark.asyncio
async def test_commission_projection_upsert():
    from realtime import event_consumer
    sid = str(uuid.uuid4())
    eid = str(uuid.uuid4())
    try:
        ok = await event_consumer.process_event("commission.accrued", {
            "event_id": eid, "settlement_id": sid, "tenant_id": TID,
            "reconciliation_id": str(uuid.uuid4()), "technician_id": SEED_TECH,
            "amount": "1500.00", "currency": "TWD"})
        assert ok is True
        row = await (await db_module._conn.execute(
            "SELECT amount, currency, technician_id::text "
            "FROM technician_commission_projection WHERE settlement_id=%s::uuid", (sid,))).fetchone()
        assert float(row[0]) == 1500.0 and row[1] == "TWD" and row[2] == SEED_TECH
    finally:
        await _cleanup_proj(sid=sid, eid=eid)


@pytest.mark.asyncio
async def test_unknown_topic_ignored():
    from realtime import event_consumer
    ok = await event_consumer.process_event("unknown.topic", {"event_id": str(uuid.uuid4())})
    assert ok is False


# ── reconcile gate ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_skipped_when_kafka_disabled(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP", raising=False)
    r = await recon.reconcile_commission(tenant_id=TID)
    assert r["skipped"] is True and r["gate_pass"] is True


@pytest.mark.asyncio
async def test_reconcile_amount_eq_helper():
    assert recon._amount_eq(1500.0, "1500.00") is True
    assert recon._amount_eq(1500.0, 1500.01) is False
    assert recon._amount_eq(None, 1) is False
