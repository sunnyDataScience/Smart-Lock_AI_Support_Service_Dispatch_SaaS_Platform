"""CR-0029 收尾 — 廠商（發案者）核准 service。

註冊建 vendors(status='pending_approval')；本 service 提供管理員核准/拒絕 + pending 列表，
收完註冊閉環。vendor.status='active' 才算正式啟用（pending 仍可登入但屬待審）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.vendor_service")

_VENDOR_SELECT = (
    "id, user_id, vendor_type, name, company_name, phone, email, address, "
    "status, rejection_reason, approved_by, approved_at, created_at"
)


def _row_to_vendor(r: tuple) -> dict:
    return {
        "id": str(r[0]),
        "user_id": str(r[1]),
        "vendor_type": r[2],
        "name": r[3],
        "company_name": r[4],
        "phone": r[5],
        "email": r[6],
        "address": r[7],
        "status": r[8],
        "rejection_reason": r[9],
        "approved_by": str(r[10]) if r[10] else None,
        "approved_at": r[11].isoformat() if r[11] else None,
        "created_at": r[12].isoformat() if r[12] else None,
    }


async def list_vendors(*, tenant_id: str, status: str | None = None) -> dict:
    """列出廠商（可依 status 過濾，如 pending_approval）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if status:
        cur = await db_module._conn.execute(
            f"SELECT {_VENDOR_SELECT} FROM vendors "
            "WHERE (tenant_id = %s::uuid OR tenant_id IS NULL) AND status = %s "
            "ORDER BY created_at DESC",
            (tenant_id, status),
        )
    else:
        cur = await db_module._conn.execute(
            f"SELECT {_VENDOR_SELECT} FROM vendors "
            "WHERE (tenant_id = %s::uuid OR tenant_id IS NULL) "
            "ORDER BY created_at DESC",
            (tenant_id,),
        )
    rows = await cur.fetchall()
    return {"items": [_row_to_vendor(r) for r in rows]}


async def _set_status(
    *, tenant_id: str, vendor_id: str, new_status: str,
    approver_id: str | None, reason: str | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 只允許從 pending_approval 轉 active/rejected（冪等防呆）
    upd = await db_module._conn.execute(
        "UPDATE vendors SET status = %s, approved_by = %s::uuid, approved_at = NOW(), "
        "  rejection_reason = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND (tenant_id = %s::uuid OR tenant_id IS NULL) "
        "  AND status = 'pending_approval' "
        "RETURNING " + _VENDOR_SELECT,
        (new_status, approver_id, reason, vendor_id, tenant_id),
    )
    row = await upd.fetchone()
    if not row:
        # 區分 404 vs 409（已非 pending）
        chk = await db_module._conn.execute(
            "SELECT status FROM vendors WHERE id = %s::uuid", (vendor_id,))
        existing = await chk.fetchone()
        if not existing:
            raise ApiError("NOT_FOUND", "vendor not found", 404)
        raise ApiError("STATE_CONFLICT", f"vendor already {existing[0]}", 409)
    logger.info("vendor %s → %s by %s", vendor_id, new_status, approver_id)
    return _row_to_vendor(row)


async def approve_vendor(*, tenant_id: str, vendor_id: str, approver_id: str) -> dict:
    return await _set_status(
        tenant_id=tenant_id, vendor_id=vendor_id, new_status="active",
        approver_id=approver_id, reason=None,
    )


async def reject_vendor(
    *, tenant_id: str, vendor_id: str, approver_id: str, reason: str | None = None,
) -> dict:
    return await _set_status(
        tenant_id=tenant_id, vendor_id=vendor_id, new_status="rejected",
        approver_id=approver_id, reason=reason,
    )
