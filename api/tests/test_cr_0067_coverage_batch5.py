"""CR-0067 測試計畫覆蓋 Batch 5（FALSE_GAP 確認 + M09 evidence + 對帳）。

- TI-M09-02：Evidence visibility RBAC 矩陣（品牌不看環境照 / 會計不看門檢 / 內部全看）
- TI-M09-03：Evidence retention + legal_hold（過期軟刪；legal_hold 即使過期不刪）
- TI-FIN-RECON-02：對帳異常三 fix_path 狀態機（detect→propose→approve(SoD)→apply）
- TI-FIN-AP-03：statement 自動核准排除 disputed（dispute window 互動）
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
_JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


# ── TI-M09-02 Evidence visibility RBAC 矩陣 ──
@pytest.mark.unit
def test_evidence_visibility_matrix():
    from services.media_service import _hidden_purposes
    # 品牌：客戶家中環境照（門檢前/後 + 完工前/中）全隱藏
    brand_hidden = _hidden_purposes("brand_oem")
    assert {"door_check_before", "door_check_after", "completion_before", "completion_during"} <= brand_hidden
    assert "completion_after" not in brand_hidden          # 完工後照品牌可看
    # 會計：只隱藏門檢照（付款/完工必要照可看）
    acc_hidden = _hidden_purposes("accounting")
    assert "door_check_before" in acc_hidden and "completion_after" not in acc_hidden
    # 內部 staff：全看（空集）
    for role in ("admin", "ops", "dispatcher", "technician", "customer_service"):
        assert _hidden_purposes(role) == set(), role


async def _bare_wo(cat="repair") -> str:
    wid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, service_category) "
        "VALUES (%s::uuid,'in_progress','台北市信義區1號',%s)", (wid, cat))
    return wid


@pytest.mark.asyncio
async def test_evidence_visibility_list_filters_by_role():
    assert await db_module._ensure_conn()
    from services import media_service as ms
    wid = await _bare_wo()
    try:
        # 上傳一張門檢前（環境照）+ 一張完工後
        await ms.upload_media(tenant_id=TID, uploader_user_id=None, file_bytes=_JPEG,
            filename="d.jpg", content_type="image/jpeg", purpose="door_check_before", work_order_id=wid)
        await ms.upload_media(tenant_id=TID, uploader_user_id=None, file_bytes=_JPEG[:-1] + b"1",
            filename="c.jpg", content_type="image/jpeg", purpose="completion_after", work_order_id=wid)
        # 品牌：只看到完工後（環境照被濾）
        brand = await ms.list_media_for_work_order(tenant_id=TID, work_order_id=wid, role="brand_oem")
        purposes = {i["purpose"] for i in brand["items"]}
        assert purposes == {"completion_after"}
        # 內部 staff：看到兩張
        staff = await ms.list_media_for_work_order(tenant_id=TID, work_order_id=wid, role="admin")
        assert len({i["purpose"] for i in staff["items"]}) == 2
    finally:
        await db_module._conn.execute("DELETE FROM media_files WHERE work_order_id=%s::uuid", (wid,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))


# ── TI-M09-03 retention + legal_hold ──
@pytest.mark.asyncio
async def test_retention_legal_hold_blocks_soft_delete():
    assert await db_module._ensure_conn()
    from services import media_service as ms
    wid = await _bare_wo()
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        # 兩筆都已過期（retention_until = 昨天）；a 無 legal_hold、b 有
        for mid, hold in ((a, False), (b, True)):
            await db_module._conn.execute(
                "INSERT INTO media_files (id, tenant_id, work_order_id, purpose, filename, "
                "  content_type, size_bytes, storage_path, sha256, retention_until, legal_hold) "
                "VALUES (%s::uuid,%s::uuid,%s::uuid,'completion_after','x.jpg','image/jpeg',10,"
                "  %s,%s, NOW()-INTERVAL '1 day', %s)",
                (mid, TID, wid, f"p/{mid}", mid, hold))
        n = await ms.soft_delete_expired_media()
        assert n >= 1
        # a 被軟刪、b（legal_hold）保留
        ca = await db_module._conn.execute("SELECT deleted_at FROM media_files WHERE id=%s::uuid", (a,))
        cb = await db_module._conn.execute("SELECT deleted_at FROM media_files WHERE id=%s::uuid", (b,))
        assert (await ca.fetchone())[0] is not None    # 過期無 hold → 軟刪
        assert (await cb.fetchone())[0] is None        # legal_hold → 不刪
    finally:
        await db_module._conn.execute("DELETE FROM media_files WHERE work_order_id=%s::uuid", (wid,))
        await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))


# ── TI-FIN-RECON-02 三 fix_path 狀態機 ──
async def _seed_recon() -> str:
    rid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO saas.reconciliation (id, tenant_id, technician_id, period_start, period_end, "
        "  total_orders, total_revenue, platform_fee, technician_payout, status) "
        "VALUES (%s::uuid,%s::uuid,%s::uuid, NOW()-INTERVAL '30 days', NOW()-INTERVAL '1 day', "
        "  1, 1000, 100, 900, 'pending')",
        (rid, TID, str(uuid.uuid4())))
    return rid


@pytest.mark.asyncio
@pytest.mark.parametrize("fix_path,kwargs", [
    ("invoice_supplement", {"applied_invoice_id": None}),
    ("voucher_reverse", {"applied_voucher_id": None}),
    ("recon_void", {}),
])
async def test_recon_exception_three_fix_paths(fix_path, kwargs):
    assert await db_module._ensure_conn()
    from services import reconciliation_exception_service as res
    proposer, approver = str(uuid.uuid4()), str(uuid.uuid4())
    rid = await _seed_recon()
    try:
        ex = await res.detect_exception(
            tenant_id=TID, reconciliation_id=rid, exception_kind="amount_mismatch",
            description=f"測試 {fix_path}", detected_by="cron_daily", amount_delta=50.0)
        eid = ex["id"]
        await res.propose_fix(tenant_id=TID, exception_id=eid, actor_id=proposer, fix_path=fix_path)
        # SoD：同人 approve → 403
        with pytest.raises(ApiError) as e:
            await res.approve_fix(tenant_id=TID, exception_id=eid, actor_id=proposer)
        assert e.value.status_code == 403
        await res.approve_fix(tenant_id=TID, exception_id=eid, actor_id=approver)
        # apply：invoice_supplement/voucher_reverse 缺 ref → 422
        if fix_path == "invoice_supplement":
            with pytest.raises(ApiError) as e2:
                await res.apply_fix(tenant_id=TID, exception_id=eid)
            assert e2.value.status_code == 422
            out = await res.apply_fix(tenant_id=TID, exception_id=eid, applied_invoice_id=str(uuid.uuid4()))
        elif fix_path == "voucher_reverse":
            out = await res.apply_fix(tenant_id=TID, exception_id=eid, applied_voucher_id=str(uuid.uuid4()))
        else:  # recon_void
            out = await res.apply_fix(tenant_id=TID, exception_id=eid)
        assert out["status"] == "applied"
    finally:
        await db_module._conn.execute("DELETE FROM saas.reconciliation_exception WHERE reconciliation_id=%s::uuid", (rid,))
        await db_module._conn.execute("DELETE FROM saas.reconciliation WHERE id=%s::uuid", (rid,))


# ── TI-FIN-AP-03 自動核准排除 disputed ──
@pytest.mark.asyncio
async def test_statement_auto_approve_excludes_disputed():
    assert await db_module._ensure_conn()
    from realtime.statement_auto_approval_cron import StatementAutoApprovalCron
    pend, disp = str(uuid.uuid4()), str(uuid.uuid4())
    cols = ("id, tenant_id, technician_id, period_year, period_month, total_completed_orders, "
            "gross_amount, travel_fee_deduction, cash_collection_deduction, dispute_hold_amount, "
            "other_deductions, net_amount, status, dispute_window_ends_at")
    try:
        # 過期 pending_review（應被核准）
        await db_module._conn.execute(
            f"INSERT INTO saas.technician_statement ({cols}) VALUES "
            "(%s::uuid,%s::uuid,%s::uuid,2026,5,1,1000,0,0,0,0,1000,'pending_review',NOW()-INTERVAL '1 day')",
            (pend, TID, str(uuid.uuid4())))
        # disputed（即使 window 過期也不應被核准）
        await db_module._conn.execute(
            f"INSERT INTO saas.technician_statement ({cols}) VALUES "
            "(%s::uuid,%s::uuid,%s::uuid,2026,5,2,1000,0,0,0,0,1000,'disputed',NOW()-INTERVAL '1 day')",
            (disp, TID, str(uuid.uuid4())))
        await StatementAutoApprovalCron().run_once()
        cp = await db_module._conn.execute("SELECT status FROM saas.technician_statement WHERE id=%s::uuid", (pend,))
        cd = await db_module._conn.execute("SELECT status FROM saas.technician_statement WHERE id=%s::uuid", (disp,))
        assert (await cp.fetchone())[0] == "approved"   # pending 過期 → 核准
        assert (await cd.fetchone())[0] == "disputed"   # disputed → 不動
    finally:
        for sid in (pend, disp):
            await db_module._conn.execute("DELETE FROM saas.technician_statement WHERE id=%s::uuid", (sid,))
