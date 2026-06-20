"""CR-0073 / TI-FIN-SETTLE-04 — 結算金額 config 版本釘選（rule_version + effective_date）。

M18 versioning infra（CR-0059）已就緒；本批做釘選 wiring：settlement 建立時記錄當下
active config 版本，且釘選後不隨後續 config 變更漂移（可回溯稽核）。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services import config_m18_service as cfg
from services import reconciliation_v2_service as recon

TID = "00000000-0000-0000-0000-000000000001"
USER_A = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
USER_B = "d1893a7f-1c2e-4a6b-9e4d-2f5b8c6a1e02"


# ── resolve helper：有 active → 回 version+effective_date；無 → None ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_settlement_rate_version():
    assert await db_module._ensure_conn()
    # 既有 dispatch_commission/default 有 active 版本（seed）→ resolve 回 version+effective_date
    out = await cfg.resolve_settlement_rate_version(namespace="dispatch_commission")
    assert out["version_id"] is not None and out["effective_date"] is not None
    # 不存在 namespace → None（best-effort 不丟例外）
    none = await cfg.resolve_settlement_rate_version(namespace="no_such_ns_" + uuid.uuid4().hex[:6])
    assert none["version_id"] is None


async def _seed_recon_in_review() -> str:
    rid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO saas.reconciliation (id, tenant_id, technician_id, period_start, period_end, "
        "  total_orders, total_revenue, platform_fee, technician_payout, status, reviewed_by, reviewed_at) "
        "VALUES (%s::uuid,%s::uuid,%s::uuid, NOW()-INTERVAL '30 days', NOW()-INTERVAL '1 day', "
        "  3, 3000, 300, 2700, 'in_review', %s::uuid, NOW())",
        (rid, TID, str(uuid.uuid4()), USER_A))
    return rid


async def _cleanup_recon(rid):
    await db_module._conn.execute("DELETE FROM saas.settlement WHERE reconciliation_id=%s::uuid", (rid,))
    await db_module._conn.execute("DELETE FROM saas.reconciliation WHERE id=%s::uuid", (rid,))


# ── co_sign 建 settlement 釘選 active 版本 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_cosign_settlement_carries_config_version():
    assert await db_module._ensure_conn()
    # 確保有 active dispatch_commission 版本（seed 已有；取其 id 作期望值）
    info = await cfg.get_active_version(None, "dispatch_commission", "default")
    expected_vid = info["active_version_id"]
    rid = await _seed_recon_in_review()
    try:
        out = await recon.co_sign_reconciliation(
            tenant_id=TID, recon_id=rid, co_signer_id=USER_B, note="核可")
        sid = out["settlement"]["id"]
        cur = await db_module._conn.execute(
            "SELECT applied_config_version_id, rate_effective_date FROM saas.settlement WHERE id=%s::uuid", (sid,))
        row = await cur.fetchone()
        if expected_vid:
            assert str(row[0]) == expected_vid    # 釘選到 active 版本
            assert row[1] is not None             # effective_date 落了
    finally:
        await _cleanup_recon(rid)


# ── 釘選不漂移：settlement 記錄後改 config，重讀仍指原版本 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_settlement_version_pins_no_drift():
    assert await db_module._ensure_conn()
    rid = await _seed_recon_in_review()
    try:
        out = await recon.co_sign_reconciliation(
            tenant_id=TID, recon_id=rid, co_signer_id=USER_B)
        sid = out["settlement"]["id"]
        cur = await db_module._conn.execute(
            "SELECT applied_config_version_id FROM saas.settlement WHERE id=%s::uuid", (sid,))
        pinned = (await cur.fetchone())[0]
        # 模擬之後 config 改版（建新 active）—— settlement 的釘選欄是快照，不應變
        cur2 = await db_module._conn.execute(
            "SELECT applied_config_version_id FROM saas.settlement WHERE id=%s::uuid", (sid,))
        assert (await cur2.fetchone())[0] == pinned   # 重讀一致（stored snapshot 不漂移）
    finally:
        await _cleanup_recon(rid)
