"""平台方廠商管理服務（UAT R2 W3-2：自助註冊退場 → 平台代建）。

`vendors` = 發案方登入帳號（role='vendor', tenant_type='requestor'）。
公開自助註冊（POST /vendors/register）與待審核流（:approve/:reject）已依
2026-07-18 業主裁決整條移除；廠商帳號一律由平台管理員代建，建立即 active。

實作策略：復用 `auth_service.register_vendor` 的驗證/建立核心（email 角色內
去重、bcrypt hash、users+vendors 雙列 transaction），以 initial_status='active'
直接啟用。vendors 住主品牌庫（platform-api 的 POSTGRES_URI 指主庫）→ 平台端
直查 `db_module._conn`；list 不加 tenant filter（平台跨品牌視角）。

audit 慣例：跟隨既有平台廠商端點作法 —— logger 記 actor（vendors.approved_by
FK 指品牌 users，平台管理員不在其中，不落該欄）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import auth_service
from services.vendor_service import _VENDOR_SELECT, _row_to_vendor

logger = logging.getLogger("api.platform_vendor")


async def list_vendors(*, status: str | None = None) -> dict:
    """跨品牌廠商清單（不加 tenant filter）。status 可過濾（如 active）。"""
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


async def create_vendor(*, req: dict, actor_user_id: str) -> dict:
    """平台代建廠商帳號：復用註冊核心，建立即 active（不走待審）。"""
    result = await auth_service.register_vendor(req, initial_status="active")
    logger.info(
        "platform create vendor %s (%s) by %s",
        result["data"]["id"], result["data"]["email"], actor_user_id,
    )
    return result
