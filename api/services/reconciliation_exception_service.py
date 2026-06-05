"""Reconciliation Exception 業務邏輯 — CR-0018 Flow 13 EX5。

範圍：
  - detect_*: upload-time / cron / manual 偵測入口（HD-5 雙保險）
  - list_exceptions / get_exception
  - propose_fix（step-1 CSM：detected/ops_review → fix_proposed + fix_path）
  - approve_fix（step-2 ops_manager：fix_proposed → fix_approved，SoD CHECK）
  - apply_fix（fix_approved → applied；路徑 1/2 內建；路徑 3 連動 voucher_void）
  - close_exception（applied → closed）

設計決策（CR-0018 HD-1~HD-5）：
  - HD-1 (a)：獨立表 saas.reconciliation_exception，不污染 disputes
  - HD-2 (b)：六態 detected → ops_review → fix_proposed → fix_approved
                → applied → closed
  - HD-3 (c)：路徑 1+2 走本服務 endpoint；路徑 3 衝銷連動 voucher_void
  - HD-4 (a)：雙簽，proposed_by ≠ approved_by（DB CHECK + service 403）
  - HD-5 (c)：upload_realtime + cron_daily + manual 三 detected_by 入口

Stage 1（本 commit）：schema + detect/list/get/propose/approve/apply/close 基礎服務
Stage 2：router endpoint + voucher_void 連動實作 + upload-time hook
Stage 3：cron job + e2e test
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.reconciliation_exception_service")

ExceptionKind = Literal[
    "amount_mismatch", "missing_invoice", "duplicate_entry",
    "orphan_settlement", "other",
]
FixPath = Literal["invoice_supplement", "recon_void", "voucher_reverse"]
DetectedBy = Literal["upload_realtime", "cron_daily", "manual"]
Status = Literal[
    "detected", "ops_review", "fix_proposed", "fix_approved", "applied", "closed",
]

_VALID_KIND = {
    "amount_mismatch", "missing_invoice", "duplicate_entry",
    "orphan_settlement", "other",
}
_VALID_FIX_PATH = {"invoice_supplement", "recon_void", "voucher_reverse"}
_VALID_DETECTED_BY = {"upload_realtime", "cron_daily", "manual"}

# 狀態機允許轉移（from → set of allowed to）
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "detected": {"ops_review", "closed"},        # ops 看到 → review；誤報 → closed
    "ops_review": {"fix_proposed", "closed"},
    "fix_proposed": {"fix_approved", "ops_review"},  # 退回
    "fix_approved": {"applied"},
    "applied": {"closed"},
    "closed": set(),
}

_SELECT = (
    "e.id, e.tenant_id, e.reconciliation_id, e.exception_kind, e.status, "
    "e.fix_path, e.detected_by, e.detected_at, e.amount_delta, e.description, "
    "e.proposed_by, e.proposed_at, e.approved_by, e.approved_at, "
    "e.applied_voucher_id, e.applied_invoice_id, e.resolution_note, "
    "e.created_at, e.updated_at"
)


def _coerce_decimal(amount) -> str | None:
    if amount is None:
        return None
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "reconciliation_id": str(row[2]),
        "exception_kind": row[3],
        "status": row[4],
        "fix_path": row[5],
        "detected_by": row[6],
        "detected_at": row[7].isoformat() if row[7] else None,
        "amount_delta": _coerce_decimal(row[8]),
        "description": row[9],
        "proposed_by": str(row[10]) if row[10] else None,
        "proposed_at": row[11].isoformat() if row[11] else None,
        "approved_by": str(row[12]) if row[12] else None,
        "approved_at": row[13].isoformat() if row[13] else None,
        "applied_voucher_id": str(row[14]) if row[14] else None,
        "applied_invoice_id": str(row[15]) if row[15] else None,
        "resolution_note": row[16],
        "created_at": row[17].isoformat() if row[17] else None,
        "updated_at": row[18].isoformat() if row[18] else None,
    }


# ============================================================
# 偵測入口（HD-5 雙保險：upload-time / cron / manual）
# ============================================================

async def detect_exception(
    *,
    tenant_id: str,
    reconciliation_id: str,
    exception_kind: ExceptionKind,
    description: str,
    detected_by: DetectedBy,
    amount_delta: float | None = None,
) -> dict:
    """寫入一筆新異常列（status='detected'）。

    冪等：相同 (tenant_id, reconciliation_id, exception_kind, description) 已有
    detected/ops_review/fix_proposed/fix_approved 之 row 時不再寫入，回該 row。
    """
    if exception_kind not in _VALID_KIND:
        raise ApiError(
            "VALIDATION_ERROR", f"invalid exception_kind: {exception_kind}", 422,
        )
    if detected_by not in _VALID_DETECTED_BY:
        raise ApiError(
            "VALIDATION_ERROR", f"invalid detected_by: {detected_by}", 422,
        )
    if exception_kind == "amount_mismatch" and amount_delta is None:
        raise ApiError(
            "VALIDATION_ERROR",
            "amount_delta 必填於 amount_mismatch",
            422,
        )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 冪等檢查
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.reconciliation_exception e "
        "WHERE e.tenant_id = %s::uuid AND e.reconciliation_id = %s::uuid "
        "  AND e.exception_kind = %s AND e.description = %s "
        "  AND e.status NOT IN ('applied', 'closed') "
        "LIMIT 1",
        (tenant_id, reconciliation_id, exception_kind, description),
    )
    existing = await cur.fetchone()
    if existing:
        logger.info(
            "detect_exception idempotent hit: recon=%s kind=%s",
            reconciliation_id[:8], exception_kind,
        )
        return _row_to_dict(existing)

    # INSERT
    cur = await db_module._conn.execute(
        "INSERT INTO saas.reconciliation_exception "
        "  (tenant_id, reconciliation_id, exception_kind, detected_by, "
        "   amount_delta, description) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s) "
        f"RETURNING {_SELECT.replace('e.', '')}",
        (
            tenant_id, reconciliation_id, exception_kind, detected_by,
            amount_delta, description,
        ),
    )
    row = await cur.fetchone()
    logger.info(
        "exception detected: id=%s recon=%s kind=%s by=%s",
        str(row[0])[:8], reconciliation_id[:8], exception_kind, detected_by,
    )
    return _row_to_dict(row)


# ============================================================
# Read
# ============================================================

async def list_exceptions(
    *,
    tenant_id: str,
    status: str | None = None,
    reconciliation_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)

    where = ["e.tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if status:
        where.append("e.status = %s")
        args.append(status)
    if reconciliation_id:
        where.append("e.reconciliation_id = %s::uuid")
        args.append(reconciliation_id)
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            where.append("e.created_at < %s")
            args.append(decoded)
    args.append(limit + 1)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.reconciliation_exception e "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY e.created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]
    next_cursor = encode_cursor(rows[-1][17].isoformat()) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}


async def get_exception(*, tenant_id: str, exception_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.reconciliation_exception e "
        "WHERE e.id = %s::uuid AND e.tenant_id = %s::uuid",
        (exception_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "exception not found", 404)
    return _row_to_dict(row)


# ============================================================
# 狀態機（dual-sign + transitions）
# ============================================================

async def _fetch_for_update(exception_id: str, tenant_id: str) -> tuple:
    cur = await db_module._conn.execute(
        "SELECT status, proposed_by, fix_path "
        "FROM saas.reconciliation_exception "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (exception_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "exception not found", 404)
    return row


def _check_transition(current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ApiError(
            "STATE_CONFLICT",
            f"cannot transition from '{current}' to '{target}'",
            409,
        )


async def propose_fix(
    *,
    tenant_id: str,
    exception_id: str,
    actor_id: str,
    fix_path: FixPath,
    resolution_note: str | None = None,
) -> dict:
    """step-1 CSM: detected/ops_review → fix_proposed + fix_path。

    Raises ApiError(422) if fix_path invalid.
    """
    if fix_path not in _VALID_FIX_PATH:
        raise ApiError("VALIDATION_ERROR", f"invalid fix_path: {fix_path}", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current_row = await _fetch_for_update(exception_id, tenant_id)
    _check_transition(current_row[0], "fix_proposed")

    upd = await db_module._conn.execute(
        "UPDATE saas.reconciliation_exception SET "
        "  status = 'fix_proposed', fix_path = %s, "
        "  proposed_by = %s::uuid, proposed_at = NOW(), "
        "  resolution_note = COALESCE(%s, resolution_note), updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"  AND status IN ('detected', 'ops_review') RETURNING {_SELECT.replace('e.', '')}",
        (fix_path, actor_id, resolution_note, exception_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return _row_to_dict(row)


async def approve_fix(
    *, tenant_id: str, exception_id: str, actor_id: str,
) -> dict:
    """step-2 ops_manager: fix_proposed → fix_approved。

    SoD: approver ≠ proposer → 403 SOD_VIOLATION。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current_row = await _fetch_for_update(exception_id, tenant_id)
    current_status, proposed_by, fix_path = current_row[0], current_row[1], current_row[2]
    _check_transition(current_status, "fix_approved")
    if proposed_by and str(proposed_by) == actor_id:
        raise ApiError(
            "SOD_VIOLATION",
            "approver must differ from proposer",
            403,
        )
    if not fix_path:
        raise ApiError(
            "STATE_CONFLICT",
            "fix_path required before approve (call propose_fix first)",
            409,
        )

    upd = await db_module._conn.execute(
        "UPDATE saas.reconciliation_exception SET "
        "  status = 'fix_approved', approved_by = %s::uuid, "
        "  approved_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"  AND status = 'fix_proposed' RETURNING {_SELECT.replace('e.', '')}",
        (actor_id, exception_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return _row_to_dict(row)


async def apply_fix(
    *,
    tenant_id: str,
    exception_id: str,
    applied_voucher_id: str | None = None,
    applied_invoice_id: str | None = None,
) -> dict:
    """fix_approved → applied。寫 applied_voucher_id / applied_invoice_id reference。

    Stage 1 不實作 voucher_void 連動 — Stage 2 router 端先呼 voucher_void_service
    後再呼本函式帶回 voucher_id；本函式僅標記狀態 + 寫 reference。
    路徑必填對應：
      - invoice_supplement → applied_invoice_id 必填
      - voucher_reverse    → applied_voucher_id 必填
      - recon_void         → 兩者皆可省（推 reconciliation status='disputed' 由
                              router 端額外連動）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current_row = await _fetch_for_update(exception_id, tenant_id)
    _check_transition(current_row[0], "applied")
    fix_path = current_row[2]

    if fix_path == "invoice_supplement" and not applied_invoice_id:
        raise ApiError(
            "VALIDATION_ERROR",
            "applied_invoice_id required for invoice_supplement path",
            422,
        )
    if fix_path == "voucher_reverse" and not applied_voucher_id:
        raise ApiError(
            "VALIDATION_ERROR",
            "applied_voucher_id required for voucher_reverse path",
            422,
        )

    upd = await db_module._conn.execute(
        "UPDATE saas.reconciliation_exception SET "
        "  status = 'applied', "
        "  applied_voucher_id = COALESCE(%s::uuid, applied_voucher_id), "
        "  applied_invoice_id = COALESCE(%s::uuid, applied_invoice_id), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"  AND status = 'fix_approved' RETURNING {_SELECT.replace('e.', '')}",
        (applied_voucher_id, applied_invoice_id, exception_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return _row_to_dict(row)


async def close_exception(
    *, tenant_id: str, exception_id: str, resolution_note: str | None = None,
) -> dict:
    """applied → closed（或 detected/ops_review/fix_proposed → closed 誤報）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current_row = await _fetch_for_update(exception_id, tenant_id)
    _check_transition(current_row[0], "closed")
    upd = await db_module._conn.execute(
        "UPDATE saas.reconciliation_exception SET "
        "  status = 'closed', "
        "  resolution_note = COALESCE(%s, resolution_note), updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status NOT IN ('closed') "
        f"RETURNING {_SELECT.replace('e.', '')}",
        (resolution_note, exception_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "already closed", 409)
    return _row_to_dict(row)


async def advance_to_review(
    *, tenant_id: str, exception_id: str,
) -> dict:
    """detected → ops_review（ops 接手）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current_row = await _fetch_for_update(exception_id, tenant_id)
    _check_transition(current_row[0], "ops_review")
    upd = await db_module._conn.execute(
        "UPDATE saas.reconciliation_exception SET "
        "  status = 'ops_review', updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"  AND status = 'detected' RETURNING {_SELECT.replace('e.', '')}",
        (exception_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    return _row_to_dict(row)
