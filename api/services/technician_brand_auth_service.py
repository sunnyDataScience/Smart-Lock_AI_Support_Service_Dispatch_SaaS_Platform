"""技師品牌授權 grant/revoke（CR-0166 R1-4）。

technician_brand_authorization（063）原僅 seed，執行期不可授/撤——但 dispatch
候選過濾與 F9 手動派工 _assert_brand_authorized 都讀它。本 service 讓平台方營運
可即時授權/撤證。

身分域：師傅為平台權威（CR-0112/CR-0114），寫入走 require_tech_conn 權威庫 +
mirror_rows 鏡射品牌庫投影（維持 split-tech-db.sh --verify 對帳）。撤證即時性走
pull-on-read（候選查詢每次 live 重查權威庫，無快取；與 F15 停權一致，不需 WS 廣播）。

裁決（CR-0166 §8-R1-4）：軟撤（authorized=FALSE 保留歷史）；audit 走
saas.technician_lifecycle_event（migration 105 擴 CHECK）。
"""

from __future__ import annotations

import json
import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.tech_mirror import mirror_rows


async def _assert_technician(tenant_id: str, technician_id: str) -> None:
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT 1 FROM technicians WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    if await cur.fetchone() is None:
        raise ApiError("TECHNICIAN_NOT_FOUND", "Technician not found in this tenant", 404)


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "technician_id": str(row[1]),
        "brand": row[2],
        "authorized": bool(row[3]),
        "cert_expires_at": row[4].isoformat() if row[4] else None,
    }


_SELECT = "id, technician_id, brand, authorized, cert_expires_at"


async def list_brand_authorizations(*, tenant_id: str, technician_id: str) -> list[dict]:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    await _assert_technician(tenant_id, technician_id)
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        f"SELECT {_SELECT} FROM technician_brand_authorization "
        "WHERE technician_id = %s::uuid ORDER BY brand ASC",
        (technician_id,),
    )
    return [_row_to_dict(r) for r in await cur.fetchall()]


async def _audit_lifecycle(tenant_id: str, technician_id: str, action: str,
                           actor_user_id: str | None, brand: str, reason: str) -> None:
    """寫 saas.technician_lifecycle_event（平台 console listPlatformTechnicianLifecycleEvents 可查）。"""
    conn = await db_module.require_tech_conn()
    await conn.execute(
        "INSERT INTO saas.technician_lifecycle_event "
        "  (tenant_id, technician_id, event_type, actor_user_id, actor_role, reason, notes) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, 'platform_admin', %s, %s)",
        (tenant_id, technician_id, action, actor_user_id, reason,
         json.dumps({"brand": brand}, ensure_ascii=False)),
    )


async def grant_brand_authorization(
    *, tenant_id: str, technician_id: str, brand: str,
    cert_expires_at: str | None = None, actor_user_id: str | None = None,
    reason: str = "platform grant",
) -> dict:
    """授權技師某品牌（冪等 upsert；已存在則更新為 authorized=TRUE）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    brand = (brand or "").strip()
    if not brand:
        raise ApiError("VALIDATION_ERROR", "brand 必填", 422)
    await _assert_technician(tenant_id, technician_id)

    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "INSERT INTO technician_brand_authorization "
        "  (technician_id, brand, authorized, cert_expires_at, is_mock) "
        "VALUES (%s::uuid, %s, TRUE, %s::date, FALSE) "
        "ON CONFLICT (technician_id, brand) DO UPDATE SET "
        "  authorized = TRUE, cert_expires_at = EXCLUDED.cert_expires_at, is_mock = FALSE "
        f"RETURNING {_SELECT}",
        (technician_id, brand, cert_expires_at or None),
    )
    row = await cur.fetchone()
    await mirror_rows("technician_brand_authorization", [str(row[0])])
    await _audit_lifecycle(tenant_id, technician_id, "brand_auth_granted", actor_user_id, brand, reason)
    return _row_to_dict(row)


async def revoke_brand_authorization(
    *, tenant_id: str, technician_id: str, brand: str,
    actor_user_id: str | None = None, reason: str = "platform revoke",
) -> dict:
    """撤銷技師某品牌授權（軟撤 authorized=FALSE，保留歷史；查無列 404；重複撤 200 no-op）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    brand = (brand or "").strip()
    await _assert_technician(tenant_id, technician_id)

    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "UPDATE technician_brand_authorization SET authorized = FALSE "
        "WHERE technician_id = %s::uuid AND brand = %s "
        f"RETURNING {_SELECT}",
        (technician_id, brand),
    )
    row = await cur.fetchone()
    if row is None:
        raise ApiError("NOT_FOUND", f"技師無品牌「{brand}」授權紀錄", 404)
    await mirror_rows("technician_brand_authorization", [str(row[0])])
    await _audit_lifecycle(tenant_id, technician_id, "brand_auth_revoked", actor_user_id, brand, reason)
    return _row_to_dict(row)
