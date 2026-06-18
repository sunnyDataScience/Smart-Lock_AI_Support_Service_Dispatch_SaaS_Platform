"""CR-0030 租戶派工模式 service。

三檔（會議 Action #7）：
  - manual        租戶手動派（預設；現行 assign_order 行為）
  - platform_paid 平台代派（付費點；assign 標記 dispatched_via='platform' 供計費對帳）
  - auto_match    自動媒合（Report 2；本輪不自動執行，僅保留設定值）

存放：saas.tenant.dispatch_mode（migration 039）。single-tenant：tenant row 已存在。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.dispatch_mode_service")

VALID_MODES = ("manual", "platform_paid", "auto_match")

# dispatch_mode → work_orders.dispatched_via 標記
_MODE_TO_VIA = {
    "manual": "manual",
    "platform_paid": "platform",  # 平台代派 = 可計費事件
    "auto_match": "auto_match",
}


async def get_dispatch_mode(tenant_id: str) -> str:
    """取租戶派工模式；無 row / 無設定 → 'manual'。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT dispatch_mode FROM saas.tenant WHERE id = %s::uuid",
        (tenant_id,),
    )
    row = await cur.fetchone()
    return (row[0] if row and row[0] else "manual")


async def set_dispatch_mode(*, tenant_id: str, mode: str) -> dict:
    """設定租戶派工模式（app 驗證列舉）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if mode not in VALID_MODES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"dispatch_mode must be one of {list(VALID_MODES)}",
            422,
        )
    upd = await db_module._conn.execute(
        "UPDATE saas.tenant SET dispatch_mode = %s WHERE id = %s::uuid RETURNING id",
        (mode, tenant_id),
    )
    if not await upd.fetchone():
        raise ApiError("NOT_FOUND", "tenant not found", 404)
    logger.info("dispatch_mode set tenant=%s mode=%s", tenant_id, mode)
    return {"tenant_id": tenant_id, "dispatch_mode": mode}


def via_for_mode(mode: str) -> str:
    """派工模式 → dispatched_via 標記。"""
    return _MODE_TO_VIA.get(mode, "manual")
