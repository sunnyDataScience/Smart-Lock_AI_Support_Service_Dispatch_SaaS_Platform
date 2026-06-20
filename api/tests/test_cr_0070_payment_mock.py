"""CR-0070 金流 mock 骨架測試（TI-FIN-PAY-01~05）。

mock-first（會議決議5）：驗 intent/confirm/webhook 冪等/fallback/現金爭議/payment gate。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import payment_service as ps

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
_SEED_USER = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _bare_wo() -> str:
    """建最小 work_order（disputes/payments FK 需真 WO）。"""
    wid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, service_category) "
        "VALUES (%s::uuid,'in_progress','台北市信義區1號','repair')", (wid,))
    return wid


async def _cleanup_wo(wid):
    await db_module._conn.execute("DELETE FROM payments WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM disputes WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))


# ── PAY-02 三軌 intent + 冪等 ──
@pytest.mark.asyncio
async def test_create_intent_three_methods_and_idempotency():
    assert await db_module._ensure_conn()
    wid = str(uuid.uuid4())
    try:
        for m in ("cash", "apple_pay", "line_pay"):
            out = await ps.create_payment_intent(
                tenant_id=TID, work_order_id=wid, method=m, amount=1500)
            assert out["status"] == "pending" and out["method"] == m
        # 非法 method → 422
        with pytest.raises(ApiError) as e:
            await ps.create_payment_intent(tenant_id=TID, work_order_id=wid, method="btc", amount=1)
        assert e.value.status_code == 422
        # 冪等：同 key 二次 → 回既有
        k = "idem-" + uuid.uuid4().hex[:8]
        a = await ps.create_payment_intent(tenant_id=TID, work_order_id=wid, method="cash",
                                           amount=800, idempotency_key=k)
        b = await ps.create_payment_intent(tenant_id=TID, work_order_id=wid, method="cash",
                                           amount=800, idempotency_key=k)
        assert b["deduplicated"] is True and b["id"] == a["id"]
    finally:
        await _cleanup_wo(wid)


# ── confirm + PAY-03 webhook 冪等 + 驗簽 ──
@pytest.mark.asyncio
async def test_linepay_webhook_idempotent_and_signature():
    assert await db_module._ensure_conn()
    wid = str(uuid.uuid4())
    try:
        intent = await ps.create_payment_intent(
            tenant_id=TID, work_order_id=wid, method="line_pay", amount=2000)
        txn = "txn-" + uuid.uuid4().hex[:10]
        payload = f"{intent['intent_id']}|{txn}|2000"
        sig = ps.sign_linepay_payload(payload)
        # 壞簽章 → 401
        with pytest.raises(ApiError) as e:
            await ps.handle_linepay_webhook(payload=payload, signature="bad", provider_txn_id=txn,
                                            intent_id=intent["intent_id"], tenant_id=TID)
        assert e.value.status_code == 401
        # 正確簽章 → confirmed
        r1 = await ps.handle_linepay_webhook(payload=payload, signature=sig, provider_txn_id=txn,
                                             intent_id=intent["intent_id"], tenant_id=TID)
        assert r1["status"] == "confirmed" and r1["duplicate_webhook"] is False
        # 重複 webhook（同 txn）→ duplicate，不重複認
        r2 = await ps.handle_linepay_webhook(payload=payload, signature=sig, provider_txn_id=txn,
                                             intent_id=intent["intent_id"], tenant_id=TID)
        assert r2["duplicate_webhook"] is True
        cnt = await db_module._conn.execute(
            "SELECT count(*) FROM payments WHERE provider_txn_id=%s", (txn,))
        assert (await cnt.fetchone())[0] == 1   # 只一筆認款
    finally:
        await _cleanup_wo(wid)


# ── PAY-04 fallback 兩次嘗試 audit ──
@pytest.mark.asyncio
async def test_payment_fallback_two_attempts():
    assert await db_module._ensure_conn()
    wid = str(uuid.uuid4())
    try:
        first = await ps.create_payment_intent(
            tenant_id=TID, work_order_id=wid, method="line_pay", amount=1200)
        fb = await ps.record_payment_fallback(
            tenant_id=TID, failed_intent_id=first["intent_id"], new_method="cash",
            amount=1200, work_order_id=wid)
        assert fb["attempt_count"] == 2 and fb["fallback_from"] == "line_pay" and fb["method"] == "cash"
        # 原 intent 標 failed
        c = await db_module._conn.execute(
            "SELECT status FROM payments WHERE intent_id=%s", (first["intent_id"],))
        assert (await c.fetchone())[0] == "failed"
    finally:
        await _cleanup_wo(wid)


# ── PAY-05 現金爭議 ──
@pytest.mark.asyncio
async def test_cash_dispute_threshold():
    assert await db_module._ensure_conn()
    wid = await _bare_wo()   # disputes.work_order_id FK 需真 WO
    try:
        pay = await ps.create_payment_intent(
            tenant_id=TID, work_order_id=wid, method="cash", amount=3000)
        # 差 1000 ≥ 500 門檻 → flagged + payment disputed
        out = await ps.report_cash_dispute(
            tenant_id=TID, payment_id=pay["id"], filed_by=_SEED_USER,
            reported_amount=2000, reason="客訴收到金額不符")
        assert out["delta"] == 1000.0 and out["flagged"] is True
        c = await db_module._conn.execute(
            "SELECT status FROM payments WHERE id=%s::uuid", (pay["id"],))
        assert (await c.fetchone())[0] == "disputed"
        # 差 100 < 500 → 不 flag
        pay2 = await ps.create_payment_intent(
            tenant_id=TID, work_order_id=wid, method="cash", amount=3000)
        out2 = await ps.report_cash_dispute(
            tenant_id=TID, payment_id=pay2["id"], filed_by=_SEED_USER,
            reported_amount=2900, reason="小額不符")
        assert out2["flagged"] is False
    finally:
        await _cleanup_wo(wid)


# ── PAY-01 payment gate（config 驅動）──
@pytest.mark.asyncio
async def test_payment_gate_disabled_and_enabled():
    assert await db_module._ensure_conn()
    wid = str(uuid.uuid4())
    cfg_id = str(uuid.uuid4())
    try:
        # 預設無 config → gate disabled，pass
        d = await ps.assert_payment_gate(tenant_id=TID, work_order_id=wid)
        assert d["gate"] == "disabled" and d["passed"] is True
        # 開 config → 無付款 → 422
        await db_module._conn.execute(
            "INSERT INTO saas.config_version (id, tenant_id, namespace, key, value, state, created_by) "
            "VALUES (%s::uuid, NULL, 'payment_gate', 'default', "
            "  '{\"require_payment_for_dispatch\": true}'::jsonb, 'active', %s::uuid)",
            (cfg_id, _SEED_USER))
        with pytest.raises(ApiError) as e:
            await ps.assert_payment_gate(tenant_id=TID, work_order_id=wid)
        assert e.value.error_code == "PAYMENT_REQUIRED_FOR_DISPATCH"
        # 有 confirmed 付款 → pass
        intent = await ps.create_payment_intent(
            tenant_id=TID, work_order_id=wid, method="cash", amount=1000, purpose="deposit")
        await ps.confirm_payment(tenant_id=TID, intent_id=intent["intent_id"])
        ok = await ps.assert_payment_gate(tenant_id=TID, work_order_id=wid)
        assert ok["passed"] is True
    finally:
        await db_module._conn.execute("DELETE FROM saas.config_version WHERE id=%s::uuid", (cfg_id,))
        await _cleanup_wo(wid)
