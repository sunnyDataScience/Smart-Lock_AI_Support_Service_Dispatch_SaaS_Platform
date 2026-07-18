"""廠商（發案者）讀取 service（CR-0029 → UAT R2 W3-2 收斂）。

廠商自助註冊與核准/拒絕流已於 2026-07-18 依業主裁決整條移除（廠商帳號由
平台代建、建立即 active，見 services/platform_vendor_service.py）。本 service
只留讀取面：廠商自身 profile（/vendors/me）與品牌唯讀清單。
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


async def get_vendor_by_user_id(*, user_id: str) -> dict | None:
    """CR-0029：依登入 user_id 取廠商自身 profile（廠商專區 /vendors/me 用）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        f"SELECT {_VENDOR_SELECT} FROM vendors WHERE user_id = %s::uuid LIMIT 1",
        (user_id,),
    )
    r = await cur.fetchone()
    return _row_to_vendor(r) if r else None


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


# 核准/拒絕狀態機（approve_vendor / reject_vendor / _set_status）已依 UAT R2
# W3-2 裁決（2026-07-18）移除 —— 代建帳號建立即 active，無 pending 待審流。
