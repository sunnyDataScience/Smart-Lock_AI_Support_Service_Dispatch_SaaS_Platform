"""CR-0069 測試計畫覆蓋 Batch 7 — TI-M02-05 device serial 為 warranty/RMA 唯一識別。

- create_warranty_claim 接受並落 device_serial
- check_rma_abuse serial 級偵測（同 serial 累計；同型號不同 serial 不互相累計）
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services import warranty_service as ws

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _seed_customer() -> str:
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, role) "
        "VALUES (%s::uuid,%s::uuid,'客','line_user')", (uid, TID))
    return uid


@pytest.mark.asyncio
async def test_create_warranty_claim_stores_serial():
    assert await db_module._ensure_conn()
    cust = await _seed_customer()
    try:
        claim, created = await ws.create_warranty_claim(
            tenant_id=TID, customer_id=cust, device_brand="Yale", device_model="YDM",
            claim_type="defective", requested_by_role="customer_service",
            device_serial="SN-AAA-001")
        assert created is True
        cur = await db_module._conn.execute(
            "SELECT device_serial FROM warranty_claims WHERE id=%s::uuid", (claim["id"],))
        assert (await cur.fetchone())[0] == "SN-AAA-001"
    finally:
        await db_module._conn.execute("DELETE FROM warranty_claims WHERE customer_id=%s::uuid", (cust,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (cust,))


@pytest.mark.asyncio
async def test_rma_abuse_serial_scope():
    assert await db_module._ensure_conn()
    cust = await _seed_customer()
    ids = []
    try:
        # 同一顆鎖（SN-X）送修 3 次 + 另一顆同型號（SN-Y）1 次
        for serial, n in (("SN-X", 3), ("SN-Y", 1)):
            for _ in range(n):
                cid = str(uuid.uuid4()); ids.append(cid)
                await db_module._conn.execute(
                    "INSERT INTO warranty_claims (id, customer_id, device_brand, device_model, "
                    "  device_serial, claim_date, claim_type, status, warranty_start_mode, "
                    "  warranty_start_date, warranty_end_date, is_within_warranty) "
                    "VALUES (%s::uuid,%s::uuid,'Yale','YDM',%s,CURRENT_DATE,'repair','filed',"
                    "  'purchase_date',CURRENT_DATE,CURRENT_DATE+730,true)",
                    (cid, cust, serial))
        # serial 級：SN-X 命中 3 → flagged，scope=serial
        r = await ws.check_rma_abuse(customer_id=cust, device_serial="SN-X")
        assert r["count"] == 3 and r["abuse_flagged"] is True and r["scope"] == "serial"
        # SN-Y 只 1 → 不 flagged（同型號不同實體鎖不互累）
        r2 = await ws.check_rma_abuse(customer_id=cust, device_serial="SN-Y")
        assert r2["count"] == 1 and r2["abuse_flagged"] is False
        # model 級（無 serial）：同型號共 4 → flagged，scope=model
        r3 = await ws.check_rma_abuse(customer_id=cust, device_brand="Yale", device_model="YDM")
        assert r3["count"] == 4 and r3["abuse_flagged"] is True and r3["scope"] == "model"
    finally:
        for cid in ids:
            await db_module._conn.execute("DELETE FROM warranty_claims WHERE id=%s::uuid", (cid,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (cust,))
