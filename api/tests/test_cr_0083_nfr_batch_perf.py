"""CR-0083 / TI-NFR-01 — 月結/對帳批次效能（純 DB-bound，無需 LLM/stack）。

seed N 筆 reconciliation → 計時 generate_monthly_batch / export_batch_csv → 斷言門檻。
門檻寬鬆（防 N+1 熱點誤判）；主要守「批次不會病態退化」+ 冪等 + eligible 過濾。
"""
from __future__ import annotations
import time
import uuid
import pytest
import core.db as db_module
from services import monthly_settlement_service as mss

TID = "00000000-0000-0000-0000-000000000001"
PY, PM = 2099, 1
THRESHOLD_GEN_S = 20.0      # 200 筆（含 N+1 dispute 子查詢）寬鬆上限
THRESHOLD_CSV_S = 5.0


async def _seed_recons(n: int):
    rows = []
    for _ in range(n):
        rid, tid = str(uuid.uuid4()), str(uuid.uuid4())
        rows.append(rid)
        await db_module._conn.execute(
            "INSERT INTO saas.reconciliation (id, tenant_id, technician_id, period_start, period_end, "
            "  total_orders, total_revenue, platform_fee, technician_payout, status, approved_at) "
            "VALUES (%s::uuid,%s::uuid,%s::uuid, '2099-01-01', '2099-01-31', 1, 1000, 200, 800, "
            "  'approved', '2099-01-15')", (rid, TID, tid))
    return rows


async def _cleanup_period():
    # 清本測 period 的 batch + settlement + reconciliation（2099-01）
    await db_module._conn.execute(
        "DELETE FROM saas.settlement WHERE reconciliation_id IN "
        "(SELECT id FROM saas.reconciliation WHERE period_start='2099-01-01' AND tenant_id=%s::uuid)", (TID,))
    await db_module._conn.execute(
        "DELETE FROM saas.monthly_settlement_batch WHERE tenant_id=%s::uuid "
        "AND period_year=%s AND period_month=%s", (TID, PY, PM))
    await db_module._conn.execute(
        "DELETE FROM saas.reconciliation WHERE period_start='2099-01-01' AND tenant_id=%s::uuid", (TID,))


@pytest.mark.component
@pytest.mark.asyncio
async def test_generate_monthly_batch_perf_and_idempotent():
    assert await db_module._ensure_conn()
    await _cleanup_period()
    await _seed_recons(200)
    try:
        t0 = time.perf_counter()
        out = await mss.generate_monthly_batch(tenant_id=TID, period_year=PY, period_month=PM)
        elapsed = time.perf_counter() - t0
        assert out.get("inserted", out.get("total_settlements", 0)) >= 200
        assert elapsed < THRESHOLD_GEN_S, f"200 筆月結批次耗時 {elapsed:.1f}s 超過 {THRESHOLD_GEN_S}s"
        # 冪等：第二次跑 0 新增（NOT EXISTS 守門）
        out2 = await mss.generate_monthly_batch(tenant_id=TID, period_year=PY, period_month=PM)
        assert out2.get("inserted", 0) == 0
    finally:
        await _cleanup_period()


@pytest.mark.component
@pytest.mark.asyncio
async def test_export_batch_csv_perf_and_eligible_only():
    assert await db_module._ensure_conn()
    await _cleanup_period()
    await _seed_recons(50)
    try:
        out = await mss.generate_monthly_batch(tenant_id=TID, period_year=PY, period_month=PM)
        batch_id = out["batch_id"] if "batch_id" in out else out.get("id")
        # 混入一筆 ineligible（settled_eligible=false）不應出現在 CSV
        await db_module._conn.execute(
            "UPDATE saas.settlement SET settled_eligible=false "
            "WHERE monthly_batch_id=%s::uuid AND ctid IN "
            "(SELECT ctid FROM saas.settlement WHERE monthly_batch_id=%s::uuid LIMIT 1)",
            (batch_id, batch_id))
        t0 = time.perf_counter()
        csv_str = await mss.export_batch_csv(batch_id=batch_id, tenant_id=TID)
        elapsed = time.perf_counter() - t0
        assert elapsed < THRESHOLD_CSV_S
        # CSV 行數 = eligible（49）+ header；ineligible 不計
        data_lines = [l for l in csv_str.strip().splitlines() if l.strip()]
        assert len(data_lines) - 1 == 49      # 扣 header
    finally:
        await _cleanup_period()
