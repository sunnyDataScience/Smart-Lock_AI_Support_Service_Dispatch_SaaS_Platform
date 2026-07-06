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

