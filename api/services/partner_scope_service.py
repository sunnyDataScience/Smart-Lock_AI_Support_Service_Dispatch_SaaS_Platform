"""Partner Portal scope 隔離（CR-0084 / TI-PORTAL-01）。

修假綠：原只有 tenant 級隔離，vendor 可讀整個 tenant 全品牌 statement。本服務以登入身分
綁定的 brand_partner_id 強制過濾（fail-closed）：vendor 只能看自己的 partner 資料，
跨 partner 讀 → 403；未綁 partner → 403（不退化成全 tenant 可見）。admin 不受限。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.partner_scope_service")

# 不受 partner scope 限制的管理角色（可看全 tenant）
_PARTNER_SCOPE_BYPASS_ROLES = frozenset({"admin", "platform_admin"})  # SA-01：死角色移除
# 受 partner scope 限制的角色
_PARTNER_BOUND_ROLES = frozenset({"vendor", "brand_oem", "brand", "dealer", "builder"})


def resolve_partner_scope(
    *, role: str, bound_partner_id: str | None, requested_partner_id: str | None,
) -> str | None:
    """純函式：解析應套用的 brand_partner_id 過濾值（None = 可看全部）。

    - admin 類 → 回 requested 原值（含 None=全部），不強制。
    - partner 綁定角色：
        - 未綁 partner → 403 PARTNER_NOT_BOUND（fail-closed）。
        - requested 指定他人 partner → 403 CROSS_PARTNER_READ。
        - 否則 → 強制回 bound_partner_id（即使 requested=None 也不可看全部）。
    """
    if role in _PARTNER_SCOPE_BYPASS_ROLES:
        return requested_partner_id
    if role in _PARTNER_BOUND_ROLES:
        if not bound_partner_id:
            raise ApiError("PARTNER_NOT_BOUND", "vendor account not bound to a partner scope", 403)
        if requested_partner_id and str(requested_partner_id) != str(bound_partner_id):
            raise ApiError("CROSS_PARTNER_READ", "cannot read another partner's data", 403)
        return bound_partner_id
    # 其他角色：保守 fail-closed（非 admin、非 partner）→ 強制無資料
    raise ApiError("FORBIDDEN", f"role '{role}' has no partner portal access", 403)


async def get_vendor_brand_partner_id(*, user_id: str) -> str | None:
    """讀 vendors.brand_partner_id（登入 vendor 綁定的 partner）；無則 None。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT brand_partner_id FROM vendors WHERE user_id = %s::uuid LIMIT 1", (user_id,))
    row = await cur.fetchone()
    return str(row[0]) if row and row[0] else None
