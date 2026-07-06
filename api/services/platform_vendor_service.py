"""平台方廠商審核服務（廠商審核自品牌後台移到 platform console）。

`vendors` = 發案方登入帳號（role='vendor', tenant_type='requestor'），品牌/經銷/
鎖店註冊後 pending_approval，核准即啟用可登入發案。此職權自品牌後台
（admin/vendor-approvals）移到平台方統一管。

實作策略：復用 `vendor_service` 的狀態機（approve/reject 含冪等 409、audit）。
vendors 住主品牌庫（platform-api 的 POSTGRES_URI 指主庫）→ 平台端直查
`db_module._conn`；list 不加 tenant filter（平台跨品牌視角），approve/reject
先查該 vendor 的 tenant_id 再委派 vendor_service。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import vendor_service
from services.vendor_service import _VENDOR_SELECT, _row_to_vendor

logger = logging.getLogger("api.platform_vendor")


async def list_vendors(*, status: str | None = None) -> dict:
    """跨品牌廠商清單（不加 tenant filter）。status 可過濾（如 pending_approval）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if status:
        cur = await db_module._conn.execute(
            f"SELECT {_VENDOR_SELECT} FROM vendors WHERE status = %s "
            "ORDER BY created_at DESC",
            (status,),
        )
    else:
        cur = await db_module._conn.execute(
            f"SELECT {_VENDOR_SELECT} FROM vendors ORDER BY created_at DESC",
        )
    rows = await cur.fetchall()
    return {"items": [_row_to_vendor(r) for r in rows]}


async def _resolve_tenant_id(vendor_id: str) -> str | None:
    """查該廠商的 tenant_id（不存在 → 404）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT tenant_id FROM vendors WHERE id = %s::uuid", (vendor_id,))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "vendor not found", 404)
    return str(row[0]) if row[0] else None


# vendors.approved_by 有 FK → 品牌 users(id)。平台管理員住平台庫(lock_platform),
# 非品牌 user,存其 uuid 會違反 FK → 平台核准一律存 approved_by=NULL(approved_at
# 仍記錄時間;「由平台方核准」為隱含事實,品牌端已無核准權)。approver_id 參數保留
# 供未來平台側 audit 表承接(比照 technician_lifecycle_event 的 actor 記錄)。
async def approve_vendor(*, vendor_id: str, approver_id: str) -> dict:
    tenant_id = await _resolve_tenant_id(vendor_id)
    logger.info("platform approve vendor %s by %s", vendor_id, approver_id)
    return await vendor_service.approve_vendor(
        tenant_id=tenant_id, vendor_id=vendor_id, approver_id=None,
    )


async def reject_vendor(*, vendor_id: str, approver_id: str, reason: str | None = None) -> dict:
    tenant_id = await _resolve_tenant_id(vendor_id)
    logger.info("platform reject vendor %s by %s", vendor_id, approver_id)
    return await vendor_service.reject_vendor(
        tenant_id=tenant_id, vendor_id=vendor_id, approver_id=None, reason=reason,
    )
