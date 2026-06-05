"""Dispute v2 業務邏輯 — dual-sign 狀態機（CSM review → ops_manager co-sign）。

範圍：
  - list_disputes_v2（cursor + limit + status + dispute_type + work_order_id，讀 saas.dispute）
  - get_dispute_v2（單筆，404 NOT_FOUND）
  - open_dispute（filed 新建，status=filed, sla_deadline=now+60d）
  - review_dispute（step-1 CSM：filed → in_review 或 mediation）
  - co_sign_dispute（step-2 ops_manager：in_review|mediation → resolved）
  - withdraw_dispute（filed/in_review/mediation → closed_withdrawn）
  - escalate_dispute（filed/in_review/mediation → escalated）
  - reopen_dispute（resolved/closed_withdrawn → 新建 dispute, parent_dispute_id=原 id）
  - _escalate_overdue_disputes（Phase II helper：60d sla_deadline 過期 → escalated，不接 cron）

設計決策（FR-0013 / CR-0004 §8 HD-1~HD-4）：
  - tenant_id 直接過濾 saas.dispute（不 JOIN users，HD-1 D-C5）
  - SoD：cosigned_by 必須 ≠ reviewed_by，否則 403 SOD_VIOLATION（HD-3）
  - dual-sign close：CSM review（步驟 1）→ ops_manager co-sign（步驟 2）→ status: resolved（HD-3）
  - reopen：不可直接重開，必須新建 dispute 引用 parent_dispute_id（AC-05）
  - decimal：numeric(12,2) → 2 位小數 string（_coerce_decimal），對齊 legacy dispute_service
  - evidence：jsonb → 直通，str 嘗試 json.loads（_coerce_evidence，仿 legacy）
  - HD-4 resolution_amount 負值：寫 audit_log + WS publish 觸發 admin manual
    review；不自動退款（避免無人監督的退款風險），保留人工 trail
    （ADR-0061/FR-0014 下游出口，follow-up Phase II）
  - 60d escalation cron（AC-03）：Phase II Cloud Scheduler；
    _escalate_overdue_disputes() 已留好 helper，不接 cron，logger.info 標 DEFERRED
  - 不動 legacy dispute_service / public.disputes

注意：saas.dispute.filed_by 無 FK constraint（spec HD-1 D-C5 設計如此，
  filed_by 接受任意 uuid，FK 不強制 ref 到 users）。
"""

from __future__ import annotations

import json
import logging
import uuid as uuid_module

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.dispute_v2_service")

# ─────────────────────────────────────────────────────────────────────────────
# 常數
# ─────────────────────────────────────────────────────────────────────────────

_VALID_DISPUTE_TYPE = {"pricing", "quality", "warranty", "cancellation_fee", "settlement"}

_VALID_STATUS = {
    "filed", "in_review", "mediation", "resolved", "escalated", "closed_withdrawn"
}

# 可進行 review 的起始狀態
_REVIEWABLE_FROM = {"filed"}
# 可進行 co-sign close 的狀態（需已 review）
_COSIGNABLE_FROM = {"in_review", "mediation"}
# 可撤銷的狀態
_WITHDRAWABLE_FROM = {"filed", "in_review", "mediation"}
# 可手動升級的狀態
_ESCALATABLE_FROM = {"filed", "in_review", "mediation"}
# 可 reopen 的終態
_REOPENABLE_FROM = {"resolved", "closed_withdrawn"}

_SLA_DAYS = 60


# ─────────────────────────────────────────────────────────────────────────────
# 型別強制轉換輔助
# ─────────────────────────────────────────────────────────────────────────────

def _coerce_decimal(amount) -> str | None:
    """numeric(12,2) → '%.2f' string；None → None（仿 legacy dispute_service）。"""
    if amount is None:
        return None
    return f"{float(amount):.2f}"


def _coerce_evidence(raw) -> dict | list | None:
    """jsonb → Python dict/list；str → json.loads；其他 → None（仿 legacy）。"""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SELECT 欄位清單 & row → dict
# ─────────────────────────────────────────────────────────────────────────────

_SELECT = (
    "d.id, d.tenant_id, d.work_order_id, d.invoice_id, d.filed_by, "
    "d.dispute_type, d.status, d.description, d.evidence, "
    "d.proposed_resolution, d.resolution, d.resolution_amount, "
    "d.reviewed_by, d.reviewed_at, d.cosigned_by, d.cosigned_at, "
    "d.escalated_to, d.escalated_at, d.parent_dispute_id, "
    "d.filed_at, d.sla_deadline, d.resolved_at, d.created_at, d.updated_at"
)


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id":                   str(row[0]),
        "tenant_id":            str(row[1]),
        "work_order_id":        str(row[2]) if row[2] else None,
        "invoice_id":           str(row[3]) if row[3] else None,
        "filed_by":             str(row[4]),
        "dispute_type":         row[5] or "quality",
        "status":               row[6] or "filed",
        "description":          row[7] or "",
        "evidence":             _coerce_evidence(row[8]),
        "proposed_resolution":  row[9],
        "resolution":           row[10],
        "resolution_amount":    _coerce_decimal(row[11]),
        "reviewed_by":          str(row[12]) if row[12] else None,
        "reviewed_at":          row[13].isoformat() if row[13] else None,
        "cosigned_by":          str(row[14]) if row[14] else None,
        "cosigned_at":          row[15].isoformat() if row[15] else None,
        "escalated_to":         row[16],
        "escalated_at":         row[17].isoformat() if row[17] else None,
        "parent_dispute_id":    str(row[18]) if row[18] else None,
        "filed_at":             row[19].isoformat() if row[19] else None,
        "sla_deadline":         row[20].isoformat() if row[20] else None,
        "resolved_at":          row[21].isoformat() if row[21] else None,
        "created_at":           row[22].isoformat() if row[22] else None,
        "updated_at":           row[23].isoformat() if row[23] else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 公開 service functions
# ─────────────────────────────────────────────────────────────────────────────

async def list_disputes_v2(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    dispute_type: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    """cursor 分頁列出 saas.dispute，tenant_id 直接過濾。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if status and status not in _VALID_STATUS:
        raise ApiError("VALIDATION_ERROR", f"Invalid status filter: {status}", 422)

    if dispute_type and dispute_type not in _VALID_DISPUTE_TYPE:
        raise ApiError("VALIDATION_ERROR", f"Invalid dispute_type filter: {dispute_type}", 422)

    where = ["d.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        where.append("d.status = %s")
        args.append(status)

    if dispute_type:
        where.append("d.dispute_type = %s")
        args.append(dispute_type)

    if work_order_id:
        where.append("d.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(d.created_at, d.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} FROM saas.dispute d "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY d.created_at DESC, d.id DESC "
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
        next_cursor = encode_cursor({"ts": last[22].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_dispute_v2(*, tenant_id: str, dispute_id: str) -> dict:
    """單筆讀取，404 NOT_FOUND 若不存在或不屬於本 tenant。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.dispute d "
        f"WHERE d.id = %s::uuid AND d.tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)
    return _row_to_dict(row)


async def open_dispute(
    *,
    tenant_id: str,
    filed_by: str,
    dispute_type: str,
    description: str | None = None,
    work_order_id: str | None = None,
    invoice_id: str | None = None,
    evidence: dict | list | None = None,
) -> dict:
    """新建 dispute（status=filed, sla_deadline=now+60d）。

    filed_by 無 FK constraint（spec HD-1 D-C5 設計），接受任意 uuid。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if dispute_type not in _VALID_DISPUTE_TYPE:
        raise ApiError(
            "VALIDATION_ERROR",
            f"dispute_type must be one of {sorted(_VALID_DISPUTE_TYPE)}",
            422,
        )

    dispute_id = str(uuid_module.uuid4())
    evidence_json = json.dumps(evidence) if evidence is not None else None

    await db_module._conn.execute(
        "INSERT INTO saas.dispute "
        "  (id, tenant_id, work_order_id, invoice_id, filed_by, dispute_type, "
        "   status, description, evidence, filed_at, sla_deadline) "
        "VALUES "
        "  (%s::uuid, %s::uuid, "
        "   %s::uuid, %s::uuid, "
        "   %s::uuid, %s, "
        "   'filed', %s, %s::jsonb, "
        "   NOW(), NOW() + INTERVAL '60 days')",
        (
            dispute_id, tenant_id,
            work_order_id, invoice_id,
            filed_by, dispute_type,
            description, evidence_json,
        ),
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=dispute_id)


async def review_dispute(
    *,
    tenant_id: str,
    dispute_id: str,
    reviewer_id: str,
    proposed_resolution: str,
    resolution_amount: float | None = None,
    to_mediation: bool = False,
) -> dict:
    """Step-1 CSM review：filed → in_review（to_mediation=True 則 → mediation）。

    409 STATE_CONFLICT 若 status 非 filed。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispute "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)

    current_status = row[0]
    if current_status not in _REVIEWABLE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot review dispute in status '{current_status}'; expected one of {sorted(_REVIEWABLE_FROM)}",
            409,
        )

    new_status = "mediation" if to_mediation else "in_review"

    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = %s, "
        "  reviewed_by = %s::uuid, "
        "  reviewed_at = NOW(), "
        "  proposed_resolution = %s, "
        "  resolution_amount = COALESCE(%s, resolution_amount) "
        "WHERE id = %s::uuid",
        (new_status, reviewer_id, proposed_resolution, resolution_amount, dispute_id),
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=dispute_id)


async def co_sign_dispute(
    *,
    tenant_id: str,
    dispute_id: str,
    co_signer_id: str,
    resolution: str,
    resolution_amount: float | None = None,
) -> dict:
    """Step-2 ops_manager co-sign：in_review|mediation → resolved。

    409 DUAL_SIGN_REQUIRED 若 status 非 in_review/mediation（未經 review）。
    403 SOD_VIOLATION 若 co_signer == reviewed_by（同一人不可兩簽）。

    HD-4：若 resolution_amount < 0 → logger.info 標 DEFERRED（DGS/refund cascade 不實作）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not resolution or len(resolution.strip()) < 5:
        raise ApiError(
            "VALIDATION_ERROR",
            "resolution must be at least 5 characters",
            422,
        )

    cur = await db_module._conn.execute(
        "SELECT status, reviewed_by FROM saas.dispute "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)

    current_status, reviewed_by = row[0], row[1]

    if current_status not in _COSIGNABLE_FROM:
        raise ApiError(
            "DUAL_SIGN_REQUIRED",
            "需先經 CSM review（status=in_review 或 mediation）才能 co-sign",
            409,
        )

    # SoD：co-signer 必須 ≠ reviewed_by（DB level CHECK 亦有 backstop）
    if reviewed_by and str(reviewed_by) == co_signer_id:
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: co-signer 不可與 reviewer 相同",
            403,
        )

    # HD-4：resolution_amount < 0 → 觸發 admin manual review trail（不自動退款）
    # 寫 audit_events + WS publish；refund 動作由 admin 後續手動觸發避免風險
    if resolution_amount is not None and resolution_amount < 0:
        await _emit_negative_resolution_event(
            tenant_id=tenant_id, dispute_id=dispute_id,
            co_signer_id=co_signer_id, amount=resolution_amount,
        )

    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = 'resolved', "
        "  cosigned_by = %s::uuid, "
        "  cosigned_at = NOW(), "
        "  resolution = %s, "
        "  resolution_amount = COALESCE(%s, resolution_amount), "
        "  resolved_at = NOW() "
        "WHERE id = %s::uuid",
        (
            co_signer_id,
            resolution.strip()[:2000],
            resolution_amount,
            dispute_id,
        ),
    )

    # emit DisputeClosed 概念（logger audit trail，非同步 WS 推送留 Phase II）
    logger.info(
        "DisputeClosed: dispute_id=%s, reviewer=%s, co_signer=%s, resolution_amount=%s",
        dispute_id,
        str(reviewed_by) if reviewed_by else None,
        co_signer_id,
        resolution_amount,
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=dispute_id)


async def withdraw_dispute(
    *,
    tenant_id: str,
    dispute_id: str,
    reason: str | None = None,
) -> dict:
    """filed/in_review/mediation → closed_withdrawn（撤銷）。

    409 若已 resolved/escalated/closed_withdrawn。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispute "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)

    current_status = row[0]
    if current_status not in _WITHDRAWABLE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot withdraw dispute in status '{current_status}'; "
            f"expected one of {sorted(_WITHDRAWABLE_FROM)}",
            409,
        )

    # reason 存入 resolution 欄（如有提供）
    reason_clean: str | None = reason.strip()[:2000] if reason and reason.strip() else None

    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = 'closed_withdrawn' "
        + (", resolution = %s" if reason_clean else "") +
        " WHERE id = %s::uuid",
        (reason_clean, dispute_id) if reason_clean else (dispute_id,),
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=dispute_id)


async def escalate_dispute(
    *,
    tenant_id: str,
    dispute_id: str,
    escalated_by: str,
    reason: str | None = None,
) -> dict:
    """filed/in_review/mediation → escalated（手動升級；escalated_to='ops_director'）。

    60d 自動 escalation = Phase II helper（_escalate_overdue_disputes）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT status FROM saas.dispute "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)

    current_status = row[0]
    if current_status not in _ESCALATABLE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot escalate dispute in status '{current_status}'; "
            f"expected one of {sorted(_ESCALATABLE_FROM)}",
            409,
        )

    reason_clean: str | None = reason.strip()[:2000] if reason and reason.strip() else None

    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = 'escalated', "
        "  escalated_to = 'ops_director', "
        "  escalated_at = NOW() "
        + (", resolution = %s" if reason_clean else "") +
        " WHERE id = %s::uuid",
        (reason_clean, dispute_id) if reason_clean else (dispute_id,),
    )

    logger.info(
        "DisputeEscalated: dispute_id=%s, escalated_by=%s, reason=%s",
        dispute_id, escalated_by, reason_clean,
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=dispute_id)


async def reopen_dispute(
    *,
    tenant_id: str,
    dispute_id: str,
    filed_by: str,
    description: str | None = None,
    dispute_type: str | None = None,
) -> dict:
    """AC-05 reopen：原 dispute 須為 resolved/closed_withdrawn，
    新建一筆 status=filed、parent_dispute_id=原 id、
    繼承 work_order_id/invoice_id/filed_by/dispute_type，回新 dispute。

    409 若原 dispute 非 resolved/closed_withdrawn。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT status, work_order_id, invoice_id, filed_by, dispute_type "
        "FROM saas.dispute "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (dispute_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Dispute {dispute_id} not found", 404)

    current_status, work_order_id, invoice_id, orig_filed_by, orig_type = row

    if current_status not in _REOPENABLE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reopen dispute in status '{current_status}'; "
            f"expected one of {sorted(_REOPENABLE_FROM)}",
            409,
        )

    # 繼承 filed_by（若 caller 未提供不同的 filed_by，則沿用原 dispute 的 filed_by）
    effective_filed_by = filed_by or str(orig_filed_by)
    # dispute_type 可由 caller 覆寫，否則繼承原始
    effective_type = dispute_type if dispute_type and dispute_type in _VALID_DISPUTE_TYPE else orig_type

    new_dispute_id = str(uuid_module.uuid4())

    await db_module._conn.execute(
        "INSERT INTO saas.dispute "
        "  (id, tenant_id, work_order_id, invoice_id, filed_by, dispute_type, "
        "   status, description, parent_dispute_id, filed_at, sla_deadline) "
        "VALUES "
        "  (%s::uuid, %s::uuid, "
        "   %s::uuid, %s::uuid, "
        "   %s::uuid, %s, "
        "   'filed', %s, %s::uuid, "
        "   NOW(), NOW() + INTERVAL '60 days')",
        (
            new_dispute_id, tenant_id,
            str(work_order_id) if work_order_id else None,
            str(invoice_id) if invoice_id else None,
            effective_filed_by, effective_type,
            description,
            dispute_id,  # parent_dispute_id = 原 dispute
        ),
    )

    return await get_dispute_v2(tenant_id=tenant_id, dispute_id=new_dispute_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase II helper（不接 cron，留 Cloud Scheduler）
# ─────────────────────────────────────────────────────────────────────────────

async def _emit_negative_resolution_event(
    *,
    tenant_id: str,
    dispute_id: str,
    co_signer_id: str,
    amount: float,
) -> None:
    """resolution_amount < 0 → 寫 audit event + WS publish 觸發 admin manual review。

    不自動退款 — 風險過高。admin dashboard 從 audit log + WS notification 取得
    pending review 列表後手動觸發 refund / voucher reverse。

    Best-effort：失敗只 log 不 raise（不阻 dispute co-sign 主流程）。
    """
    payload = {
        "dispute_id": dispute_id,
        "resolution_amount": round(float(amount), 2),
        "co_signer_id": co_signer_id,
        "action_required": "manual_refund_review",
        "note": (
            "Negative resolution_amount detected. Admin must manually review "
            "and decide on refund / voucher_reverse action."
        ),
    }
    try:
        from services import audit_log_service
        await audit_log_service.log_event(
            event_type="dispute.negative_resolution_pending",
            actor_id=co_signer_id,
            actor_role="ops_manager",
            action="negative_resolution_audit",
            target_type="dispute",
            target_id=dispute_id,
            payload=payload,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "audit_log_service.log_event failed for negative resolution dispute=%s",
            dispute_id,
        )

    try:
        from realtime.ws_hub import hub
        await hub.publish(
            f"/realtime/disputes/{tenant_id}",
            {
                "type": "dispute.negative_resolution_pending",
                "payload": payload,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "WS publish failed for negative resolution dispute=%s", dispute_id,
        )

    logger.info(
        "Negative resolution audit: dispute=%s amount=%.2f → admin manual review pending",
        dispute_id, amount,
    )


async def _escalate_overdue_disputes(*, tenant_id: str | None = None) -> int:
    """AC-03 60d 自動 escalation helper（Phase II Cloud Scheduler）。

    掃 sla_deadline < NOW() 且 status IN (filed, in_review, mediation)
    → 更新 status=escalated, escalated_to='ops_director', escalated_at=NOW()。
    回傳升級筆數。

    cron 接入：`api/realtime/dispute_escalation_cron.py` 已 wrap 此邏輯為
    in-process cron（86400s interval）；此 helper 保留供 admin manual
    trigger / 測試用。
    """

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where_clauses = [
        "status IN ('filed', 'in_review', 'mediation')",
        "sla_deadline < NOW()",
    ]
    args: list = []

    if tenant_id:
        where_clauses.append("tenant_id = %s::uuid")
        args.append(tenant_id)

    sql = (
        "UPDATE saas.dispute SET "
        "  status = 'escalated', "
        "  escalated_to = 'ops_director', "
        "  escalated_at = NOW() "
        f"WHERE {' AND '.join(where_clauses)}"
    )

    cur = await db_module._conn.execute(sql, tuple(args))
    # psycopg rowcount
    count = cur.rowcount if hasattr(cur, "rowcount") else 0

    logger.info(
        "_escalate_overdue_disputes: escalated %d disputes (tenant=%s)",
        count, tenant_id,
    )
    return count
