"""Reconciliation v2 業務邏輯 — dual-sign（CSM review → ops_manager co-sign）。

範圍：
  - list_reconciliations_v2（cursor + limit + status + technician_id，讀 saas.reconciliation）
  - get_reconciliation_v2（單筆，404 NOT_FOUND）
  - review_reconciliation（step-1 CSM：pending → in_review）
  - co_sign_reconciliation（step-2 ops_manager：in_review → approved + INSERT saas.settlement）

設計決策（CR-0004 §8 HD-1~HD-3）：
  - tenant_id 直接過濾 saas.reconciliation（不 JOIN technicians）
  - SoD：co-signer（approved_by）必須 ≠ reviewer（reviewed_by），否則 403 SOD_VIOLATION
  - settlement INSERT 只在 dual-sign 完成（co-sign）時觸發（HD-3）
  - decimal：numeric(12,2) → 2 位小數 string（_coerce_decimal），對齊 legacy 風格
  - 不動 legacy reconciliation_service / public.reconciliations / public.settlements
"""

from __future__ import annotations

import json
import logging
import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.reconciliation_v2_service")

_VALID_STATUS = {"pending", "in_review", "approved", "disputed"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


_SELECT = (
    "r.id, r.tenant_id, r.technician_id, r.period_start, r.period_end, "
    "r.total_orders, r.total_revenue, r.platform_fee, r.technician_payout, "
    "r.status, r.reviewed_by, r.reviewed_at, r.approved_by, r.approved_at, "
    "r.note, r.created_at"
)


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "technician_id": str(row[2]),
        "period_start": row[3].isoformat() if row[3] else None,
        "period_end": row[4].isoformat() if row[4] else None,
        "total_orders": int(row[5] or 0),
        "total_revenue": _coerce_decimal(row[6]),
        "platform_fee": _coerce_decimal(row[7]),
        "technician_payout": _coerce_decimal(row[8]),
        "status": row[9] or "pending",
        "reviewed_by": str(row[10]) if row[10] else None,
        "reviewed_at": row[11].isoformat() if row[11] else None,
        "approved_by": str(row[12]) if row[12] else None,
        "approved_at": row[13].isoformat() if row[13] else None,
        "note": row[14],
        "created_at": row[15].isoformat() if row[15] else None,
    }


def _settlement_row_to_dict(row: tuple) -> dict:
    """settlement row：id, tenant_id, reconciliation_id, technician_id, amount,
    currency, status, payment_method, paid_at, created_at"""
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "reconciliation_id": str(row[2]),
        "technician_id": str(row[3]),
        "amount": _coerce_decimal(row[4]),
        "currency": row[5] or "TWD",
        "status": row[6] or "pending",
        "payment_method": row[7],
        "paid_at": row[8].isoformat() if row[8] else None,
        "created_at": row[9].isoformat() if row[9] else None,
    }


async def list_reconciliations_v2(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    technician_id: str | None = None,
) -> dict:
    """cursor 分頁列出 saas.reconciliation，tenant_id 直接過濾。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if status and status not in _VALID_STATUS:
        raise ApiError("VALIDATION_ERROR", f"Invalid status filter: {status}", 422)

    where = ["r.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        where.append("r.status = %s")
        args.append(status)

    if technician_id:
        where.append("r.technician_id = %s::uuid")
        args.append(technician_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(r.created_at, r.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} FROM saas.reconciliation r "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY r.created_at DESC, r.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_dict(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor({"ts": last[15].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_reconciliation_v2(*, tenant_id: str, recon_id: str) -> dict:
    """單筆讀取，404 NOT_FOUND 若不存在或不屬於本 tenant。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.reconciliation r "
        f"WHERE r.id = %s::uuid AND r.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)
    return _row_to_dict(row)


async def review_reconciliation(
    *,
    tenant_id: str,
    recon_id: str,
    reviewer_id: str,
    note: str | None = None,
) -> dict:
    """Step-1 CSM review：pending → in_review。

    409 STATE_CONFLICT 若 status 非 pending。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.reconciliation "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)

    current_status = row[0]
    if current_status != "pending":
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot review reconciliation in status '{current_status}'; expected 'pending'",
            409,
        )

    note_clean: str | None = None
    if note and note.strip():
        note_clean = note.strip()[:500]

    await db_module._conn.execute(
        "UPDATE saas.reconciliation SET "
        "  status = 'in_review', "
        "  reviewed_by = %s::uuid, "
        "  reviewed_at = NOW(), "
        "  note = COALESCE(%s, note) "
        "WHERE id = %s::uuid",
        (reviewer_id, note_clean, recon_id),
    )

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.reconciliation r "
        f"WHERE r.id = %s::uuid AND r.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    updated_row = await cur.fetchone()
    return _row_to_dict(updated_row)


async def co_sign_reconciliation(
    *,
    tenant_id: str,
    recon_id: str,
    co_signer_id: str,
    note: str | None = None,
) -> dict:
    """Step-2 ops_manager co-sign：in_review → approved + INSERT saas.settlement。

    409 DUAL_SIGN_REQUIRED 若 status 非 in_review。
    403 SOD_VIOLATION 若 co_signer == reviewed_by（同一人不可兩簽）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # CR-0189 §8a（業主 2026-07-30 裁決）：event_id 必須在交易外先固定——worker 重送
    # 時要原樣帶入，消費端 dedup 才有效。
    commission_event_id = str(uuid.uuid4())

    # ── 原子化（CR-0189 在 legacy 修過、v2 從未修）─────────────────────────────
    # 原本 UPDATE 與 INSERT settlement 在 autocommit 下是兩個交易：中間死掉 →
    # approved 但無 settlement（漏出款）；兩個並發 co-sign 都讀到 in_review →
    # 各建一筆 settlement（重複出款）。
    # FOR UPDATE 讓第二個請求排隊，醒來時 status 已是 approved → 走 409，
    # 而 migration 124 的 UNIQUE(reconciliation_id) 是 DB 端最後兜底。
    #
    # outbox 必須在**同一交易**內寫入——這是 outbox 模式的全部意義（事件與
    # settlement 同生共死）。publish 則必須在 **commit 之後**，否則交易 rollback
    # 就會發出一個對應不存在 settlement 的事件。
    async with db_module._conn.transaction():
        cur = await db_module._conn.execute(
            "SELECT status, reviewed_by, technician_id, technician_payout "
            "FROM saas.reconciliation "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid "
            "FOR UPDATE",
            (recon_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)

        current_status, reviewed_by, technician_id, technician_payout = (
            row[0], row[1], row[2], row[3]
        )

        if current_status != "in_review":
            raise ApiError(
                "DUAL_SIGN_REQUIRED",
                "需先經 CSM review 才能 co-sign",
                409,
            )

        # SoD：co-signer 必須 ≠ reviewer
        if reviewed_by and str(reviewed_by) == co_signer_id:
            raise ApiError(
                "SOD_VIOLATION",
                "Separation of Duties violated: co-signer 不可與 reviewer 相同",
                403,
            )

        note_clean: str | None = None
        if note and note.strip():
            note_clean = note.strip()[:500]

        # approved_by 更新 + note（co-sign 覆寫 note 若提供）
        await db_module._conn.execute(
            "UPDATE saas.reconciliation SET "
            "  status = 'approved', "
            "  approved_by = %s::uuid, "
            "  approved_at = NOW(), "
            "  note = COALESCE(%s, note) "
            "WHERE id = %s::uuid",
            (co_signer_id, note_clean, recon_id),
        )

        # INSERT saas.settlement（dual-sign 完成才建）
        payout = float(technician_payout or 0)
        # TI-FIN-SETTLE-04：釘選建立當下的結算費率 config 版本（best-effort，缺則 NULL）
        from services import config_m18_service
        ver = await config_m18_service.resolve_settlement_rate_version(tenant_id=None)
        settlement_cur = await db_module._conn.execute(
            "INSERT INTO saas.settlement "
            "  (tenant_id, reconciliation_id, technician_id, amount, currency, status, "
            "   applied_config_version_id, rate_effective_date) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'TWD', 'pending', %s, %s) "
            "RETURNING id, tenant_id, reconciliation_id, technician_id, amount, "
            "          currency, status, payment_method, paid_at, created_at",
            (tenant_id, recon_id, str(technician_id), payout,
             ver["version_id"], ver["effective_date"]),
        )
        s_row = await settlement_cur.fetchone()
        settlement = _settlement_row_to_dict(s_row)

        # 佣金事件 outbox（同交易）。共用 public.commission_event_outbox——該表無 FK，
        # 故 v2 的 saas.reconciliation id 可安全寫入；唯一鍵
        # uniq_commission_outbox_recon(tenant_id, reconciliation_id) 提供冪等。
        await db_module._conn.execute(
            "INSERT INTO commission_event_outbox "
            "  (event_id, tenant_id, topic, event_key, reconciliation_id, settlement_id, payload) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, %s::uuid, %s::jsonb) "
            "ON CONFLICT (tenant_id, reconciliation_id) DO NOTHING",
            (commission_event_id, tenant_id, "commission.accrued", str(technician_id),
             recon_id, settlement["id"],
             json.dumps({
                 "tenant_id": tenant_id,
                 "reconciliation_id": recon_id,
                 "settlement_id": settlement["id"],
                 "technician_id": str(technician_id),
                 "amount": settlement.get("amount"),
                 "currency": settlement.get("currency") or "TWD",
                 "accrued_at": settlement.get("created_at"),
                 # 標記來源路徑，讓消費端與稽核分得出 legacy／v2（兩表分裂尚未收斂，
                 # 見 CR-0189 §8 選項 b）
                 "source": "reconciliation_v2_co_sign",
             })),
        )

        # 取最新 reconciliation（同交易內讀，保證與上面的 UPDATE 一致）
        recon_cur = await db_module._conn.execute(
            f"SELECT {_SELECT} FROM saas.reconciliation r "
            f"WHERE r.id = %s::uuid AND r.tenant_id = %s::uuid",
            (recon_id, tenant_id),
        )
        recon_row = await recon_cur.fetchone()
        reconciliation = _row_to_dict(recon_row)
    # ← COMMIT 之後才 publish

    try:
        from core.event_bus import TOPIC_COMMISSION_ACCRUED, publish_event
        ok = await publish_event(
            TOPIC_COMMISSION_ACCRUED,
            {
                "tenant_id": tenant_id,
                "reconciliation_id": recon_id,
                "settlement_id": settlement["id"],
                "technician_id": str(technician_id),
                "amount": settlement.get("amount"),
                "currency": settlement.get("currency") or "TWD",
                "accrued_at": settlement.get("created_at"),
                "source": "reconciliation_v2_co_sign",
            },
            key=str(technician_id),
            event_id=commission_event_id,
        )
        if ok:
            await db_module._conn.execute(
                "UPDATE commission_event_outbox SET status = 'sent', sent_at = NOW(), "
                "  updated_at = NOW() WHERE event_id = %s::uuid AND status = 'pending'",
                (commission_event_id,),
            )
    except Exception:  # noqa: BLE001 — 即時投遞失敗不影響核准；outbox 已保底，worker 重送
        logger.warning(
            "commission.accrued 即時投遞失敗（v2 co-sign），留 outbox 由 worker 重送 event_id=%s",
            commission_event_id, exc_info=True,
        )

    return {"reconciliation": reconciliation, "settlement": settlement}
