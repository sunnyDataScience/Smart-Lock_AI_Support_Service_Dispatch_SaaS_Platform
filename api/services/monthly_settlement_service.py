"""Monthly Settlement Service — CR-0012 Stage 1 (HD-1 Manual CSV 階段化)。

範圍：
  - generate_monthly_batch(tenant_id, year, month): 建月結 batch + 對應
    settlement rows。**不重複跑**（UNIQUE constraint tenant+year+month）。
  - export_batch_csv(batch_id): 產 CSV 字串（行欄：technician_id / 80%
    payout / 20% platform fee / amount / receipt_target）
  - mark_csv_exported(batch_id, csv_url): 寫 csv_url + csv_exported_at +
    所有 settlement 狀態 pending → csv_exported（HD-1 V1 路徑）
  - mark_manual_paid(settlement_id, actor_id, receipt_url): 標 manual_paid
    （HD-4 admin UI 後續流）

設計決策：
  - ADR-0041 80/20 split：technician_payout = revenue × 0.8；platform_fee
    = revenue × 0.2（cron 跑前 reconciliation 已 store；本 service 信賴）
  - HD-5 dispute 排除：只納入 settled_eligible=true 的 settlement
  - HD-3 retry 預留：MVP 不跑 bank API，retry_count=0，路徑直走 manual_paid
  - HD-6 不啟用 escrow：amount = technician_payout 直接 (full)
  - Cron 排程由 main.py lifespan 或 GCP Cloud Scheduler 觸發
    `generate_monthly_batch(period_year=今年, period_month=今月)`
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Iterable

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.monthly_settlement_service")


def _coerce_decimal(v) -> str:
    if v is None:
        return "0.00"
    return f"{float(v):.2f}"


# ============================================================
# Generate monthly batch (HD-2 cron 觸發或 manual)
# ============================================================

async def generate_monthly_batch(
    *,
    tenant_id: str,
    period_year: int,
    period_month: int,
    triggered_by: str = "cron",
) -> dict:
    """建月結 batch row + 批次插 settlement 對應 reconciliation。

    流程：
      1. UPSERT batch row（UNIQUE tenant+year+month）— 已存則回 existing
      2. 找該 tenant 該月 reconciliation.status='approved' 且未綁 batch 的列
      3. 對每筆 reconciliation 建 settlement row（HD-5 settled_eligible
         由 work_orders dispute 狀態決定；若 wo 有 active dispute 設 false）
      4. 更新 batch total_settlements + total_amount

    Returns:
        batch dict
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if period_month < 1 or period_month > 12:
        raise ApiError("VALIDATION_ERROR", "period_month must be 1..12", 422)

    # 1. UPSERT batch
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.monthly_settlement_batch "
        "WHERE tenant_id = %s::uuid AND period_year = %s AND period_month = %s",
        (tenant_id, period_year, period_month),
    )
    row = await cur.fetchone()
    if row:
        batch_id = str(row[0])
        logger.info(
            "monthly batch already exists: tenant=%s %d-%02d batch=%s",
            tenant_id[:8], period_year, period_month, batch_id[:8],
        )
    else:
        cur = await db_module._conn.execute(
            "INSERT INTO saas.monthly_settlement_batch "
            "  (tenant_id, period_year, period_month, triggered_by) "
            "VALUES (%s::uuid, %s, %s, %s) RETURNING id",
            (tenant_id, period_year, period_month, triggered_by),
        )
        row = await cur.fetchone()
        batch_id = str(row[0])
        logger.info(
            "monthly batch created: tenant=%s %d-%02d batch=%s by=%s",
            tenant_id[:8], period_year, period_month, batch_id[:8], triggered_by,
        )

    # 2. 找該 tenant 該月 reconciliation approved 且尚未對應 settlement
    period_start = datetime(period_year, period_month, 1, tzinfo=timezone.utc)
    if period_month == 12:
        period_end = datetime(period_year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        period_end = datetime(period_year, period_month + 1, 1, tzinfo=timezone.utc)

    cur = await db_module._conn.execute(
        "SELECT r.id, r.technician_id, r.technician_payout "
        "FROM saas.reconciliation r "
        "WHERE r.tenant_id = %s::uuid "
        "  AND r.status = 'approved' "
        "  AND r.approved_at >= %s AND r.approved_at < %s "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM saas.settlement s "
        "    WHERE s.reconciliation_id = r.id AND s.monthly_batch_id IS NOT NULL"
        "  )",
        (tenant_id, period_start.isoformat(), period_end.isoformat()),
    )
    recons = await cur.fetchall()

    # TI-FIN-SETTLE-04：整批釘選同一結算費率 config 版本（best-effort，缺則 NULL）
    from services import config_m18_service
    batch_ver = await config_m18_service.resolve_settlement_rate_version(tenant_id=None)

    # 3. 各 reconciliation 建 settlement（HD-5 settled_eligible 視 wo dispute）
    inserted = 0
    total_amount = 0.0
    for recon_id, tech_id, payout in recons:
        # 查該 reconciliation 對應的 work_orders 是否有 active dispute
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM disputes d "
            "JOIN work_orders wo ON d.work_order_id = wo.id "
            "WHERE wo.id IN ("
            "  SELECT work_order_id FROM work_order_events "
            "  WHERE event_type LIKE '%%recon%%' AND payload->>'reconciliation_id' = %s"
            ") AND d.status NOT IN ('resolved', 'closed')",
            (str(recon_id),),
        )
        dispute_count_row = await cur.fetchone()
        eligible = (dispute_count_row[0] or 0) == 0

        await db_module._conn.execute(
            "INSERT INTO saas.settlement "
            "  (tenant_id, reconciliation_id, technician_id, amount, "
            "   status, monthly_batch_id, settled_eligible, "
            "   applied_config_version_id, rate_effective_date) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'pending', "
            "        %s::uuid, %s, %s, %s)",
            (
                tenant_id, str(recon_id), str(tech_id),
                float(payout or 0), batch_id, eligible,
                batch_ver["version_id"], batch_ver["effective_date"],
            ),
        )
        inserted += 1
        if eligible:
            total_amount += float(payout or 0)

    # 4. 更新 batch totals
    await db_module._conn.execute(
        "UPDATE saas.monthly_settlement_batch SET "
        "  total_settlements = total_settlements + %s, "
        "  total_amount = total_amount + %s "
        "WHERE id = %s::uuid",
        (inserted, total_amount, batch_id),
    )

    return await _get_batch(batch_id)


async def _get_batch(batch_id: str) -> dict:
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, period_year, period_month, triggered_at, "
        "       triggered_by, total_settlements, total_amount, "
        "       csv_exported_at, csv_url "
        "FROM saas.monthly_settlement_batch WHERE id = %s::uuid",
        (batch_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "batch not found", 404)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "period_year": row[2],
        "period_month": row[3],
        "triggered_at": row[4].isoformat() if row[4] else None,
        "triggered_by": row[5],
        "total_settlements": row[6],
        "total_amount": _coerce_decimal(row[7]),
        "csv_exported_at": row[8].isoformat() if row[8] else None,
        "csv_url": row[9],
    }


# ============================================================
# CSV export (HD-1 V1 manual file flow)
# ============================================================

async def export_batch_csv(*, batch_id: str, tenant_id: str) -> str:
    """產 CSV 字串（給財務匯入 ATM 端用）。

    欄位（對齊 ADR-0041 80/20 + bank 對帳所需）：
      settlement_id, technician_id, amount_twd, currency,
      reconciliation_id, period
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 驗 batch 屬本 tenant
    cur = await db_module._conn.execute(
        "SELECT id, period_year, period_month FROM saas.monthly_settlement_batch "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (batch_id, tenant_id),
    )
    batch = await cur.fetchone()
    if not batch:
        raise ApiError("NOT_FOUND", "batch not found", 404)
    period = f"{batch[1]:04d}-{batch[2]:02d}"

    cur = await db_module._conn.execute(
        "SELECT s.id, s.technician_id, s.amount, s.currency, "
        "       s.reconciliation_id "
        "FROM saas.settlement s "
        "WHERE s.monthly_batch_id = %s::uuid "
        "  AND s.tenant_id = %s::uuid "
        "  AND s.settled_eligible = true "
        "ORDER BY s.created_at",
        (batch_id, tenant_id),
    )
    rows = await cur.fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "settlement_id", "technician_id", "amount_twd", "currency",
        "reconciliation_id", "period",
    ])
    for r in rows:
        w.writerow([
            str(r[0]), str(r[1]), _coerce_decimal(r[2]),
            r[3] or "TWD", str(r[4]), period,
        ])

    return buf.getvalue()


async def mark_csv_exported(
    *, batch_id: str, tenant_id: str, csv_url: str | None = None,
) -> dict:
    """匯出後標 csv_exported_at + batch.csv_url + 所有 pending settlement →
    csv_exported。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    upd = await db_module._conn.execute(
        "UPDATE saas.monthly_settlement_batch SET "
        "  csv_exported_at = NOW(), csv_url = COALESCE(%s, csv_url) "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        "RETURNING id",
        (csv_url, batch_id, tenant_id),
    )
    if not await upd.fetchone():
        raise ApiError("NOT_FOUND", "batch not found", 404)

    await db_module._conn.execute(
        "UPDATE saas.settlement SET status = 'csv_exported' "
        "WHERE monthly_batch_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status = 'pending' AND settled_eligible = true",
        (batch_id, tenant_id),
    )
    return await _get_batch(batch_id)


# ============================================================
# Manual paid (HD-4 admin UI 後)
# ============================================================

async def mark_manual_paid(
    *,
    settlement_id: str,
    tenant_id: str,
    actor_id: str,
    receipt_url: str,
) -> dict:
    """admin UI 確認財務已撥款 + 上傳水單 → status='manual_paid'。

    Conditions:
      - 必須 status='csv_exported' (HD-1 V1 路徑) or 'pending' (誤狀態救援)
      - settled_eligible=true 否則不允許 (dispute 中)
      - receipt_url 必填 (HD-4)
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if not receipt_url:
        raise ApiError(
            "VALIDATION_ERROR", "receipt_url required for manual_paid", 422,
        )

    upd = await db_module._conn.execute(
        "UPDATE saas.settlement SET "
        "  status = 'manual_paid', "
        "  manual_paid_at = NOW(), manual_paid_by = %s::uuid, "
        "  receipt_url = %s, paid_at = NOW(), payment_method = 'bank_manual' "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status IN ('csv_exported', 'pending') "
        "  AND settled_eligible = true "
        "RETURNING id, status, manual_paid_at, receipt_url",
        (actor_id, receipt_url, settlement_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError(
            "STATE_CONFLICT",
            "settlement not in eligible state for manual_paid",
            409,
        )
    return {
        "id": str(row[0]),
        "status": row[1],
        "manual_paid_at": row[2].isoformat() if row[2] else None,
        "receipt_url": row[3],
    }
