"""CR-0082 / TI-SYNC-02 — facts↔ERP 同步（ERP-wins，mock ERP）。

reconcile_facts 純函式（無 DB/ERP）；sync_user_facts SCD2 + audit（live DB）。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services.facts_erp_sync_service import (
    ErpSnapshot, reconcile_facts, sync_user_facts, sync_from_client,
)


# ── 純函式 ERP-wins ──
@pytest.mark.unit
def test_reconcile_erp_wins_overrides():
    chs = reconcile_facts(erp_snapshot=ErpSnapshot(phone="0912-345-678"),
                          current_facts={"phone": "0900000000"})
    assert len(chs) == 1 and chs[0].attr_key == "phone" and chs[0].new_val == "0912-345-678"


@pytest.mark.unit
def test_reconcile_no_change_when_normalized_equal():
    chs = reconcile_facts(erp_snapshot=ErpSnapshot(address=" 台北市信義區1號 "),
                          current_facts={"address": "台北市信義區1號"})
    assert chs == []                             # 正規化後相等 → 不 churn


@pytest.mark.unit
def test_reconcile_missing_erp_value_is_noop():
    chs = reconcile_facts(erp_snapshot=ErpSnapshot(phone=None, address=None),
                          current_facts={"phone": "0900000000", "address": "舊址"})
    assert chs == []                             # ERP 缺值 → 不刪現有（非破壞）


@pytest.mark.unit
def test_reconcile_multi_attr():
    chs = reconcile_facts(
        erp_snapshot=ErpSnapshot(phone="p2", address="a2", device_id="d2"),
        current_facts={"phone": "p1", "address": "a1", "device_id": "d1"})
    assert len(chs) == 3


# ── component：SCD2 + audit ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_sync_writes_scd2_and_audit():
    assert await db_module._ensure_conn()
    uid = "erp-sync-" + uuid.uuid4().hex[:10]
    try:
        # seed 現有 fact
        await db_module._conn.execute(
            "INSERT INTO user_facts (user_id, attr_key, attr_val, is_current, start_date) "
            "VALUES (%s, 'phone', '0900000000', true, NOW())", (uid,))
        out = await sync_user_facts(user_id=uid, erp_snapshot=ErpSnapshot(phone="0912345678"))
        assert out["applied"] == 1
        # 舊列 is_current=false、新列 current
        cur = await db_module._conn.execute(
            "SELECT attr_val, is_current FROM user_facts WHERE user_id=%s AND attr_key='phone' "
            "ORDER BY start_date", (uid,))
        rows = await cur.fetchall()
        assert any(r[0] == "0900000000" and r[1] is False for r in rows)   # 舊關閉
        assert any(r[0] == "0912345678" and r[1] is True for r in rows)    # 新 current
        # audit 落了
        acur = await db_module._conn.execute(
            "SELECT count(*) FROM audit_events WHERE action='facts.erp_sync' "
            "AND payload->>'user_id'=%s", (uid,))
        assert (await acur.fetchone())[0] >= 1
    finally:
        await db_module._conn.execute("DELETE FROM user_facts WHERE user_id=%s", (uid,))
        await db_module._conn.execute(
            "DELETE FROM audit_events WHERE action='facts.erp_sync' AND payload->>'user_id'=%s", (uid,))


# ── 冪等：第二次同步 0 變更 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_sync_idempotent_no_churn():
    assert await db_module._ensure_conn()
    uid = "erp-idem-" + uuid.uuid4().hex[:10]

    class _FakeClient:
        async def fetch_customer(self, user_id):
            return ErpSnapshot(phone="0911222333")

    try:
        r1 = await sync_from_client(user_id=uid, client=_FakeClient())
        assert r1["applied"] == 1                 # 首次：建立
        r2 = await sync_from_client(user_id=uid, client=_FakeClient())
        assert r2["applied"] == 0                 # 第二次：一致 → 0 變更
    finally:
        await db_module._conn.execute("DELETE FROM user_facts WHERE user_id=%s", (uid,))
        await db_module._conn.execute(
            "DELETE FROM audit_events WHERE action='facts.erp_sync' AND payload->>'user_id'=%s", (uid,))
