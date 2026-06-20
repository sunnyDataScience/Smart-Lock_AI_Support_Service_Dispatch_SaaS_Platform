"""CR-0064 測試計畫覆蓋 Batch 2（功能不存在→補最小實作+測試）。

- TI-M05-02：結案 address 必填硬閘（ADDRESS_REQUIRED_FOR_CLOSE 422）
- TI-M09-01：媒體 sha256 去重（同 WO 同檔二次上傳回既有）
- TI-RMA-04：RMA 濫用偵測（同客戶同機種視窗內 ≥3 次告警）
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
_SEED_USER = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
_JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64  # 假 jpeg


async def _bare_wo(addr) -> str:
    wid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, service_category) "
        "VALUES (%s::uuid, 'in_progress', %s, 'repair')", (wid, addr))
    return wid


async def _sig(wid):
    await db_module._conn.execute(
        "INSERT INTO digital_signatures (signer_id, signer_role, document_type, document_id, "
        "  signature_method, signature_data, integrity_hash) "
        "VALUES (%s, 'customer', 'work_order', %s::uuid, 'canvas', '{}'::jsonb, %s)",
        (_SEED_USER, wid, f"h-{wid[:8]}"))


async def _del_wo(wid):
    await db_module._conn.execute("DELETE FROM digital_signatures WHERE document_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM media_files WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))


# ── TI-M05-02 address gate ──
@pytest.mark.asyncio
async def test_completion_address_required():
    assert await db_module._ensure_conn()
    from services import work_order_service as svc
    wid = await _bare_wo(None)   # 無地址
    await _sig(wid)
    try:
        with pytest.raises(ApiError) as e:
            await svc._enforce_completion_gate(
                wo_id=wid, summary="完工", photo_evidence_ids=["p1","p2","p3"],
                signature_evidence_id="s", is_override=False, override_reason=None, actor_role=None)
        assert e.value.error_code == "ADDRESS_REQUIRED_FOR_CLOSE"
    finally:
        await _del_wo(wid)


# ── TI-M09-01 media dedup ──
@pytest.mark.asyncio
async def test_media_sha256_dedup():
    assert await db_module._ensure_conn()
    from services import media_service as ms
    wid = await _bare_wo("台北市信義區1號")
    try:
        a = await ms.upload_media(tenant_id=TID, uploader_user_id=None, file_bytes=_JPEG,
            filename="a.jpg", content_type="image/jpeg", purpose="completion_after", work_order_id=wid)
        b = await ms.upload_media(tenant_id=TID, uploader_user_id=None, file_bytes=_JPEG,
            filename="a2.jpg", content_type="image/jpeg", purpose="completion_after", work_order_id=wid)
        assert b.get("deduplicated") is True       # 第二次去重
        assert b["id"] == a["id"]                   # 回既有
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM media_files WHERE work_order_id=%s::uuid AND sha256=%s",
            (wid, a["sha256"]))
        assert (await cur.fetchone())[0] == 1       # DB 只一筆
    finally:
        await _del_wo(wid)


# ── TI-RMA-04 abuse ──
@pytest.mark.asyncio
async def test_rma_abuse_threshold():
    assert await db_module._ensure_conn()
    from services import warranty_service as ws
    cust = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, role) VALUES (%s::uuid,%s::uuid,'客','line_user')",
        (cust, TID))
    ids = []
    try:
        for _ in range(3):
            cid = str(uuid.uuid4()); ids.append(cid)
            await db_module._conn.execute(
                "INSERT INTO warranty_claims (id, customer_id, device_brand, device_model, claim_date, "
                "  claim_type, status, warranty_start_mode, warranty_start_date, warranty_end_date, "
                "  is_within_warranty) "
                "VALUES (%s::uuid,%s::uuid,'Yale','YDM',CURRENT_DATE,'repair','filed','purchase_date',"
                "  CURRENT_DATE, CURRENT_DATE + 730, true)",
                (cid, cust))
        r = await ws.check_rma_abuse(customer_id=cust, device_brand="Yale", device_model="YDM")
        assert r["count"] == 3 and r["abuse_flagged"] is True
        r2 = await ws.check_rma_abuse(customer_id=cust, device_brand="Philips", device_model="X")
        assert r2["abuse_flagged"] is False        # 不同機種
    finally:
        for cid in ids:
            await db_module._conn.execute("DELETE FROM warranty_claims WHERE id=%s::uuid", (cid,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (cust,))
