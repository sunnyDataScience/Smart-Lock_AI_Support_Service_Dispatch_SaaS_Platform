"""CR-0066 測試計畫覆蓋 Batch 4（M07/M08 現場執行）。

- TI-M07-03：技師接單 accept_order（assigned→accepted + accepted_at；錯狀態 409）
- TI-M08-01：GPS 到場 proof（Haversine 距離 + 容忍判定；record_arrival 落 proof）
- TI-M08-03：簽名 fallback_method 稽核留痕（liff/qr/paper；非法 422）
- TI-M08-04：scope change 客戶 30min 未回覆暫停旗標 cron
"""
from __future__ import annotations
import json
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo(status: str = "assigned", with_tech: bool = True) -> tuple[str, str, str, str | None]:
    """user→conv→pc→wo 全鏈。回 (wo_id, uid, pid, tech_id)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'客','0912000000','台北市信義區1號','line_user')", (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed')", (pid, cid))
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    tech_id = None
    if with_tech:
        tcur = await db_module._conn.execute(
            "SELECT id FROM technicians WHERE tenant_id=%s::uuid AND status='active' LIMIT 1", (TID,))
        trow = await tcur.fetchone()
        tech_id = str(trow[0]) if trow else None
    await db_module._conn.execute(
        "UPDATE work_orders SET status=%s, technician_id=%s WHERE id=%s::uuid",
        (status, tech_id, wo["id"]))
    return wo["id"], uid, pid, tech_id


async def _cleanup(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(f"DELETE FROM digital_signatures WHERE document_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM scope_changes WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── TI-M08-01 GPS proof 純函式 ──
@pytest.mark.unit
def test_gps_proof_haversine():
    from services.work_order_service import compute_arrival_gps_proof
    # 同點 → 距離 0、在容忍內
    p0 = compute_arrival_gps_proof(25.0330, 121.5654, 25.0330, 121.5654)
    assert p0["distance_m"] == 0.0 and p0["within_tolerance"] is True
    # 約 1km 外（緯度差 ~0.009 度 ≈ 1km）→ 超出 200m 容忍
    p1 = compute_arrival_gps_proof(25.0330, 121.5654, 25.0420, 121.5654)
    assert p1["distance_m"] > 900 and p1["within_tolerance"] is False
    # 缺座標 → None
    assert compute_arrival_gps_proof(None, 121.5, 25.0, 121.5) is None


# ── TI-M07-03 accept_order（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_accept_order_transition():
    assert await db_module._ensure_conn()
    wid, uid, pid, _ = await _seed_wo(status="assigned")
    try:
        out = await svc.accept_order(tenant_id=TID, wo_id=wid)
        assert out["id"] == wid
        cur = await db_module._conn.execute(
            "SELECT status, accepted_at FROM work_orders WHERE id=%s::uuid", (wid,))
        row = await cur.fetchone()
        assert row[0] == "accepted" and row[1] is not None    # accepted_at 已落
        # 重複 accept（已 accepted）→ 409
        with pytest.raises(ApiError) as e:
            await svc.accept_order(tenant_id=TID, wo_id=wid)
        assert e.value.status_code == 409
    finally:
        await _cleanup(uid, pid)


# ── TI-M08-01 record_arrival 落 gps_proof（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_record_arrival_writes_gps_proof():
    assert await db_module._ensure_conn()
    wid, uid, pid, _ = await _seed_wo(status="accepted")
    try:
        order = await svc.record_arrival(
            tenant_id=TID, wo_id=wid, arrived_at="2026-06-20T10:00:00Z",
            gps={"lat": 25.0331, "lng": 121.5655, "ref_lat": 25.0330, "ref_lng": 121.5654})
        assert order.get("gps_proof") is not None
        assert order["gps_proof"]["within_tolerance"] is True   # 十幾米內
        # event payload 也落了 proof
        cur = await db_module._conn.execute(
            "SELECT payload FROM work_order_events WHERE work_order_id=%s::uuid AND event_type='arrival'", (wid,))
        payload = (await cur.fetchone())[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["gps_proof"]["within_tolerance"] is True
    finally:
        await _cleanup(uid, pid)


# ── TI-M08-03 signature fallback_method（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_signature_fallback_method_audit():
    assert await db_module._ensure_conn()
    from services import signature_service as sig
    wid, uid, pid, tech_id = await _seed_wo(status="in_progress")
    if not tech_id:
        await _cleanup(uid, pid); pytest.skip("需要 active 技師")
    try:
        # 非法 fallback_method → 422
        with pytest.raises(ApiError) as e:
            await sig.submit_work_order_signature(
                tenant_id=TID, wo_id=wid, customer_signature="c", technician_signature="t",
                fallback_method="telepathy")
        assert e.value.status_code == 422
        # paper fallback → 落 signature_data.fallback_method
        await sig.submit_work_order_signature(
            tenant_id=TID, wo_id=wid, customer_signature="c", technician_signature="t",
            fallback_method="paper")
        cur = await db_module._conn.execute(
            "SELECT signature_data FROM digital_signatures WHERE document_id=%s::uuid LIMIT 1", (wid,))
        data = (await cur.fetchone())[0]
        if isinstance(data, str):
            data = json.loads(data)
        assert data["fallback_method"] == "paper"
    finally:
        await _cleanup(uid, pid)


# ── TI-M08-04 scope change 30min timeout cron（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_scope_change_timeout_flag():
    assert await db_module._ensure_conn()
    from services import scope_change_service as scs
    wid, uid, pid, tech_id = await _seed_wo(status="in_progress")
    if not tech_id:
        await _cleanup(uid, pid); pytest.skip("需要 active 技師")
    sc_old, sc_fresh = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        # 逾時提案（created_at 40 分鐘前）
        await db_module._conn.execute(
            "INSERT INTO scope_changes (id, work_order_id, technician_id, reason, "
            "  original_scope, new_scope, original_price, status, tenant_id, created_at) "
            "VALUES (%s::uuid,%s::uuid,%s::uuid,'加價','{}'::jsonb,'{}'::jsonb,1000,'pending',%s::uuid,"
            "  NOW()-INTERVAL '40 minutes')", (sc_old, wid, tech_id, TID))
        # 新鮮提案（剛建）
        await db_module._conn.execute(
            "INSERT INTO scope_changes (id, work_order_id, technician_id, reason, "
            "  original_scope, new_scope, original_price, status, tenant_id) "
            "VALUES (%s::uuid,%s::uuid,%s::uuid,'加價','{}'::jsonb,'{}'::jsonb,1000,'pending',%s::uuid)",
            (sc_fresh, wid, tech_id, TID))
        out = await scs.flag_timed_out_scope_changes(timeout_minutes=30)
        assert sc_old in out["flagged_ids"]       # 逾時被標
        assert sc_fresh not in out["flagged_ids"]  # 新鮮不標
    finally:
        await _cleanup(uid, pid)
