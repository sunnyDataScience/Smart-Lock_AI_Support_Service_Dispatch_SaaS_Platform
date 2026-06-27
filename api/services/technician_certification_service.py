"""Technician Certification Service — CR-0104 技能認證矩陣（真資料模組）。

承載師傅詳情頁「技能認證矩陣」的結構化認證資料（取代前端寫死的 5 列 mock）。
與 technician_brand_authorization（063，dispatch 品牌過濾用，UNIQUE(tech,brand)）職責分離：
一技師可有多筆具名認證，每筆含 cert_name / brand / obtained_at / expires_at。

狀態（有效/即將到期/已過期）由 expires_at vs 今日 computed，不落欄：
  - expires_at 為 NULL          → "valid"（無期限）
  - expires_at < today          → "expired"
  - today <= expires_at <= today+N → "expiring_soon"
  - 其餘                         → "valid"

N = _EXPIRING_SOON_DAYS（業務假設，CR-0104 §6 標明待業主確認，預設 30 天）。
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

# 「即將到期」門檻天數 —— 業務假設（CR-0104 §6 待業主確認；非財務規則，屬顯示慣例）
_EXPIRING_SOON_DAYS = 30


def _compute_status(expires_at: date | None, today: date) -> str:
    if expires_at is None:
        return "valid"
    if expires_at < today:
        return "expired"
    if expires_at <= today + timedelta(days=_EXPIRING_SOON_DAYS):
        return "expiring_soon"
    return "valid"


def _row_to_dict(row: tuple, today: date) -> dict:
    expires_at = row[5]
    return {
        "id": str(row[0]),
        "technician_id": str(row[1]),
        "cert_name": row[2],
        "brand": row[3],
        "obtained_at": row[4].isoformat() if row[4] else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "status": _compute_status(expires_at, today),
        "is_mock": bool(row[6]),
        "created_at": row[7].isoformat() if row[7] else None,
    }


_CERT_SELECT = (
    "id, technician_id, cert_name, brand, obtained_at, expires_at, is_mock, created_at"
)


async def _assert_technician(tenant_id: str, technician_id: str) -> None:
    """確認技師存在且屬本租戶（避免跨租戶掛認證 / 對不存在技師操作）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM technicians WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Technician not found", 404)


async def list_certifications(*, tenant_id: str, technician_id: str) -> list[dict]:
    """列某技師全部認證（依到期日近者在前；NULL 到期排最後）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    await _assert_technician(tenant_id, technician_id)

    cur = await db_module._conn.execute(
        f"SELECT {_CERT_SELECT} FROM technician_certification "
        "WHERE tenant_id = %s::uuid AND technician_id = %s::uuid "
        "ORDER BY expires_at ASC NULLS LAST, created_at DESC",
        (tenant_id, technician_id),
    )
    rows = await cur.fetchall()
    today = date.today()
    return [_row_to_dict(r, today) for r in rows]


async def create_certification(
    *,
    tenant_id: str,
    technician_id: str,
    cert_name: str,
    brand: str | None = None,
    obtained_at: str | None = None,
    expires_at: str | None = None,
) -> dict:
    """新增一筆認證（admin 後台登錄）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if not cert_name or not cert_name.strip():
        raise ApiError("VALIDATION_ERROR", "cert_name 必填", 422)
    await _assert_technician(tenant_id, technician_id)

    cert_id = str(uuid.uuid4())
    cur = await db_module._conn.execute(
        "INSERT INTO technician_certification "
        "  (id, tenant_id, technician_id, cert_name, brand, obtained_at, expires_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::date, %s::date) "
        f"RETURNING {_CERT_SELECT}",
        (
            cert_id, tenant_id, technician_id, cert_name.strip(),
            brand.strip() if brand else None,
            obtained_at or None, expires_at or None,
        ),
    )
    row = await cur.fetchone()
    return _row_to_dict(row, date.today())


async def update_certification(
    *, tenant_id: str, technician_id: str, cert_id: str, patch: dict
) -> dict:
    """部分更新一筆認證（cert_name/brand/obtained_at/expires_at）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    await _assert_technician(tenant_id, technician_id)

    sets: list[str] = []
    args: list = []
    if "cert_name" in patch and patch["cert_name"] is not None:
        if not str(patch["cert_name"]).strip():
            raise ApiError("VALIDATION_ERROR", "cert_name 不可為空", 422)
        sets.append("cert_name = %s")
        args.append(str(patch["cert_name"]).strip())
    if "brand" in patch:
        sets.append("brand = %s")
        args.append(str(patch["brand"]).strip() if patch["brand"] else None)
    if "obtained_at" in patch:
        sets.append("obtained_at = %s::date")
        args.append(patch["obtained_at"] or None)
    if "expires_at" in patch:
        sets.append("expires_at = %s::date")
        args.append(patch["expires_at"] or None)

    if not sets:
        raise ApiError("VALIDATION_ERROR", "無可更新欄位", 422)

    sets.append("updated_at = NOW()")
    args.extend([cert_id, tenant_id, technician_id])
    cur = await db_module._conn.execute(
        f"UPDATE technician_certification SET {', '.join(sets)} "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND technician_id = %s::uuid "
        f"RETURNING {_CERT_SELECT}",
        args,
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Certification not found", 404)
    return _row_to_dict(row, date.today())


async def delete_certification(
    *, tenant_id: str, technician_id: str, cert_id: str
) -> None:
    """刪除一筆認證。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "DELETE FROM technician_certification "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND technician_id = %s::uuid "
        "RETURNING id",
        (cert_id, tenant_id, technician_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "Certification not found", 404)
