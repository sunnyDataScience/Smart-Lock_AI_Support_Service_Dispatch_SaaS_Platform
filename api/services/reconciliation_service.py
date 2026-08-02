"""Reconciliation 業務邏輯。

範圍：
  - listReconciliations（cursor + limit + status + technician_id）
  - approveReconciliation（pending → approved，並建立對應 settlement）

OpenAPI Reconciliation schema：
    id, technician_id, technician_name?, period_start, period_end,
    total_orders, total_revenue (decimal str), platform_fee?,
    technician_payout (decimal str), status (pending|approved|disputed),
    approved_by?, approved_at?, created_at

DB ↔ API 對齊：
  - reconciliations.{total_revenue, platform_fee, technician_payout} (FLOAT)
    → 2 位小數 decimal string
  - status DB 與 API enum 完全一致（pending/approved/disputed）
  - technicians.name JOIN 取出 → API technician_name

租戶隔離：reconciliations 沒 tenant_id，透過 JOIN technicians ON tenant_id 過濾。
approveReconciliation 同時 INSERT 一筆 settlement(amount = technician_payout,
status = 'pending', currency = 'TWD')，由結算寫入 pipeline 接手後續支付動作。
"""

from __future__ import annotations

import json
import uuid

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.reconciliation_service")


# UAT-0718 W1-2：補 rejected（駁回/退回）——原本對帳只有核准單一動作，
# 「爭議中」篩選也無任何產生入口。
_VALID_STATUS = {"pending", "approved", "disputed", "rejected"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    out: dict = {
        "id": str(row[0]),
        "technician_id": str(row[1]),
        "period_start": row[2].isoformat() if row[2] else None,
        "period_end": row[3].isoformat() if row[3] else None,
        "total_orders": int(row[4] or 0),
        "total_revenue": _coerce_decimal(row[5]),
        "platform_fee": _coerce_decimal(row[6]),
        "technician_payout": _coerce_decimal(row[7]),
        "status": row[8] or "pending",
        "approved_by": str(row[9]) if row[9] else None,
        "approved_at": row[10].isoformat() if row[10] else None,
        "created_at": row[11].isoformat() if row[11] else None,
    }
    if row[12]:
        out["technician_name"] = row[12]
    # UAT-0718 W1-2：駁回審計欄位（migration 107；駁回前皆 NULL 不輸出）
    if row[13]:
        out["rejected_by"] = str(row[13])
    if row[14]:
        out["rejected_at"] = row[14].isoformat()
    if row[15]:
        out["reject_reason"] = row[15]
    return out


_SELECT = (
    "r.id, r.technician_id, r.period_start, r.period_end, r.total_orders, "
    "r.total_revenue, r.platform_fee, r.technician_payout, r.status, "
    "r.approved_by, r.approved_at, r.created_at, t.name, "
    "r.rejected_by, r.rejected_at, r.reject_reason"
)

_JOIN = (
    "FROM reconciliations r "
    "JOIN technicians t ON r.technician_id = t.id"
)


async def list_reconciliations(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    technician_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["t.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
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
        f"SELECT {_SELECT} {_JOIN} "
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
        next_cursor = encode_cursor({"ts": last[11].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


_APPROVE_FROM = {"pending"}


async def approve_reconciliation(
    *,
    tenant_id: str,
    recon_id: str,
    approver_user_id: str,
    note: str | None = None,
) -> dict:
    """pending → approved；同時建立 settlement(amount = technician_payout)。

    note 用於稽核軌跡（500 字內），目前 reconciliations 表沒 note 欄位，僅透過
    approved_by + approved_at 紀錄；保留參數以對齊 OpenAPI request body，未來
    可加 audit_logs 寫入或擴充 schema。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # CR-0189：狀態檢查 + 對帳單翻狀態 + 建 settlement + 佣金事件 outbox
    # **必須在同一交易內**。原本四個語句在 autocommit 連線上各自提交，造成兩個缺陷：
    #   (a) UPDATE 先提交、INSERT 後提交 → 中斷則對帳單已 approved 但 settlement
    #       不存在，而重試撞 _APPROVE_FROM={'pending'} → 永久 409、API 補不回來。
    #   (b) 無 FOR UPDATE → 並發 approve 兩邊都讀到 pending → 兩筆 settlement
    #       ＝**重複出款**（settlements 對 reconciliation_id 原本連索引都沒有）。
    # psycopg3 的 transaction() 在 autocommit 連線上會送顯式 BEGIN/COMMIT
    # （repo 既有 24 處用法，範式見 inventory_v2_service）。
    commission_event_id = str(uuid.uuid4())
    note_clean: str | None = None
    if note and note.strip():
        note_clean = note.strip()[:500]

    async with db_module._conn.transaction():
        cur = await db_module._conn.execute(
            f"SELECT r.status, r.technician_id, r.technician_payout {_JOIN} "
            f"WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid "
            f"FOR UPDATE OF r",
            (recon_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)

        current_status = row[0]
        if current_status not in _APPROVE_FROM:
            raise ApiError(
                "STATE_CONFLICT",
                f"Cannot approve reconciliation in status '{current_status}'; expected 'pending'",
                409,
            )

        technician_id = str(row[1])
        payout = float(row[2] or 0)
        if note_clean:
            logger.info("reconciliation %s approved with note: %s", recon_id, note_clean)

        await db_module._conn.execute(
            "UPDATE reconciliations SET "
            "  status = 'approved', "
            "  approved_by = %s::uuid, "
            "  approved_at = NOW() "
            "WHERE id = %s::uuid",
            (approver_user_id, recon_id),
        )

        cur = await db_module._conn.execute(
            "INSERT INTO settlements "
            "  (reconciliation_id, technician_id, amount, currency, status) "
            "VALUES (%s::uuid, %s::uuid, %s, 'TWD', 'pending') "
            "RETURNING id, reconciliation_id, technician_id, amount, currency, "
            "          status, payment_method, paid_at, created_at",
            (recon_id, technician_id, payout),
        )
        s_row = await cur.fetchone()

        # 佣金事件 outbox（同交易）—— 與 settlement 同生共死，取代「publish 失敗只 log」
        # 的永久遺失。event_id 在此固定，worker 重送時原樣帶入，消費端 dedup 才有效。
        await db_module._conn.execute(
            "INSERT INTO commission_event_outbox "
            "  (event_id, tenant_id, topic, event_key, reconciliation_id, settlement_id, payload) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, %s::uuid, %s::jsonb) "
            "ON CONFLICT (tenant_id, reconciliation_id) DO NOTHING",
            (commission_event_id, tenant_id, "commission.accrued", str(row[1]),
             recon_id, str(s_row[0]),
             json.dumps({
                 "tenant_id": tenant_id,
                 "reconciliation_id": recon_id,
                 "settlement_id": str(s_row[0]),
                 "technician_id": str(row[1]),
                 "amount": float(s_row[3] or 0),
                 "currency": s_row[4] or "TWD",
                 "accrued_at": s_row[8].isoformat() if s_row[8] else None,
             })),
        )

    settlement: dict = {
        "id": str(s_row[0]),
        "reconciliation_id": str(s_row[1]),
        "technician_id": str(s_row[2]),
        "amount": _coerce_decimal(s_row[3]),
        "currency": (s_row[4] or "TWD"),
        "status": s_row[5] or "pending",
        "created_at": s_row[8].isoformat() if s_row[8] else None,
    }
    if s_row[6]:
        settlement["payment_method"] = s_row[6]
    if s_row[7] is not None:
        settlement["paid_at"] = s_row[7].isoformat()

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} {_JOIN} WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    r_row = await cur.fetchone()
    reconciliation = _row_to_dict(r_row)

    # CR-0166 R4 / CR-0189：commission.accrued 即時投遞（ADR-017：品牌 Billing 算佣金→
    # 發事件→技師平台 Settlement 訂閱做跨品牌對帳）。
    # **publish 必須在 commit 之後**——若放在交易內而交易後續 rollback，就會發出一個
    # 對應不存在 settlement 的事件。失敗不再是永久遺失：outbox row 已同交易落地，
    # 留 pending 由 commission_outbox_worker 依 backoff 重送（at-least-once；
    # 消費端 handler 為 ON CONFLICT DO UPDATE 冪等 upsert，重複套用結果相同）。
    # （reject_reconciliation 見文末——駁回不建 settlement、不發事件）
    try:
        from core.event_bus import TOPIC_COMMISSION_ACCRUED, publish_event
        ok = await publish_event(
            TOPIC_COMMISSION_ACCRUED,
            {
                "tenant_id": tenant_id,
                "reconciliation_id": recon_id,
                "settlement_id": settlement["id"],
                "technician_id": technician_id,
                "amount": settlement["amount"],
                "currency": settlement["currency"],
                "accrued_at": settlement.get("created_at"),
            },
            key=technician_id,
            event_id=commission_event_id,
        )
        if ok:
            await db_module._conn.execute(
                "UPDATE commission_event_outbox SET status = 'sent', sent_at = NOW(), "
                "  updated_at = NOW() WHERE event_id = %s::uuid AND status = 'pending'",
                (commission_event_id,),
            )
    except Exception:  # noqa: BLE001 — 即時投遞失敗不影響核准；outbox 已保底，worker 會重送
        logger.warning("commission.accrued 即時投遞失敗，留 outbox 由 worker 重送 event_id=%s",
                       commission_event_id, exc_info=True)

    return {"reconciliation": reconciliation, "settlement": settlement}


_REJECT_FROM = {"pending"}


async def reject_reconciliation(
    *,
    tenant_id: str,
    recon_id: str,
    rejecter_user_id: str,
    reason: str,
) -> dict:
    """pending → rejected（UAT-0718 W1-2 已釘契約）。

    - reason 必填（strip 後 ≥3 字）→ 否則 422 VALIDATION_ERROR
    - 僅 pending 可駁；其他狀態 → 409 STATE_CONFLICT（語意同 approve）
    - 寫審計欄位 rejected_by / rejected_at / reject_reason（migration 107）
    - 不建 settlement、不發 commission 事件（駁回＝不進入結算）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    reason_clean = (reason or "").strip()
    if len(reason_clean) < 3:
        raise ApiError("VALIDATION_ERROR", "駁回原因必填（至少 3 字）", 422)

    # 2026-08-02 資安/併發掃描：本函式原本是「純 SELECT 讀 status → 無條件 UPDATE」，
    # 而同檔的 approve_reconciliation 早已被 CR-0189 包成 transaction + FOR UPDATE。
    # **純 SELECT 不會被 FOR UPDATE 擋住**，所以兩支端點在 approve/reject 並發時可以
    # 雙雙通過各自的 pending 檢查：approve 先 commit（已寫入 settlements 並投遞
    # commission.accrued），reject 的 UPDATE 隨後把狀態覆寫成 'rejected'。
    # 結果＝營運端看到「已駁回」但技師照樣被結算出款，且該列此時的 'rejected'
    # 兩支端點都只會回 409，API 層沒有撤銷那筆 settlement 的路徑。
    #
    # 修法與 approve 對稱（同一把列鎖才能真正互斥），並額外保留樂觀條件作雙保險。
    async with db_module._conn.transaction():
        cur = await db_module._conn.execute(
            f"SELECT r.status {_JOIN} "
            f"WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid "
            f"FOR UPDATE OF r",
            (recon_id, tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", f"Reconciliation {recon_id} not found", 404)

        current_status = row[0]
        if current_status not in _REJECT_FROM:
            raise ApiError(
                "STATE_CONFLICT",
                f"Cannot reject reconciliation in status '{current_status}'; expected 'pending'",
                409,
            )

        upd = await db_module._conn.execute(
            "UPDATE reconciliations SET "
            "  status = 'rejected', "
            "  rejected_by = %s::uuid, "
            "  rejected_at = NOW(), "
            "  reject_reason = %s "
            "WHERE id = %s::uuid AND status = ANY(%s)",
            (rejecter_user_id, reason_clean[:500], recon_id, sorted(_REJECT_FROM)),
        )
        if upd.rowcount == 0:
            raise ApiError(
                "STATE_CONFLICT",
                "對帳單狀態已被其他操作變更（駁回需要狀態為 pending），請重新載入後再試",
                409,
            )

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} {_JOIN} WHERE r.id = %s::uuid AND t.tenant_id = %s::uuid",
        (recon_id, tenant_id),
    )
    return {"reconciliation": _row_to_dict(await cur.fetchone())}
