"""Roles 業務邏輯（read-only 權限矩陣）。

5 個系統角色（admin / reviewer / technician / brand_oem / line_user）為固定列表，
權限矩陣為靜態定義（鏡射 routers 中 role_required(...) 的實際守衛邏輯）。
本 phase 不做：
  - 自訂角色 CRUD（沒有 roles 表）
  - 權限矩陣編輯（沒有 role_permissions 表）

user_count 由 SELECT role, COUNT(*) FROM users WHERE tenant_id=? GROUP BY role 計算。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.role_service")


# 12 個資源 × 3 動作；locked=True 表示系統強制（即使將來開放自訂角色也不可覆寫）。
# 設計依據：rbac 與 system_settings 的寫/刪保留給 super-admin 流程，目前無 endpoint
# 開放修改，故對所有角色 locked。
def _perm(read: bool, write: bool, delete: bool, locked: bool = False) -> dict:
    return {"read": read, "write": write, "delete": delete, "locked": locked}


_RESOURCES = [
    "work_orders",
    "technicians",
    "customers",
    "accounting",
    "invoices",
    "refunds",
    "inventory",
    "warranty",
    "disputes",
    "audit_logs",
    "roles",
    "system_settings",
]


# 矩陣對應關係：每個 role × resource 的 (read, write, delete, locked)
# admin：完整 RWD，但 roles / system_settings 的 W/D 鎖定（governance 預留）
# reviewer：審核員 — 大部分 R + 退款 / 保固 / 爭議的 W
# technician：自身相關 R + 工單 W（接單 / 完工）
# brand_oem：受限 R（自家品牌的工單 / 客戶 / 庫存）
# line_user：除自身對話外無管理權限（管理後台不適用）
_MATRIX: dict[str, dict[str, dict]] = {
    "admin": {
        "work_orders":     _perm(True, True, True),
        "technicians":     _perm(True, True, True),
        "customers":       _perm(True, True, True),
        "accounting":      _perm(True, True, True),
        "invoices":        _perm(True, True, True),
        "refunds":         _perm(True, True, True),
        "inventory":       _perm(True, True, True),
        "warranty":        _perm(True, True, True),
        "disputes":        _perm(True, True, True),
        "audit_logs":      _perm(True, False, False, locked=True),
        "roles":           _perm(True, False, False, locked=True),
        "system_settings": _perm(True, False, False, locked=True),
    },
    "reviewer": {
        "work_orders":     _perm(True, False, False),
        "technicians":     _perm(True, False, False),
        "customers":       _perm(True, False, False),
        "accounting":      _perm(True, False, False),
        "invoices":        _perm(True, False, False),
        "refunds":         _perm(True, True, False),
        "inventory":       _perm(True, False, False),
        "warranty":        _perm(True, True, False),
        "disputes":        _perm(True, True, False),
        "audit_logs":      _perm(True, False, False, locked=True),
        "roles":           _perm(False, False, False, locked=True),
        "system_settings": _perm(False, False, False, locked=True),
    },
    "technician": {
        "work_orders":     _perm(True, True, False),
        "technicians":     _perm(True, False, False),
        "customers":       _perm(True, False, False),
        "accounting":      _perm(False, False, False),
        "invoices":        _perm(False, False, False),
        "refunds":         _perm(False, False, False),
        "inventory":       _perm(True, False, False),
        "warranty":        _perm(False, False, False),
        "disputes":        _perm(True, False, False),
        "audit_logs":      _perm(False, False, False, locked=True),
        "roles":           _perm(False, False, False, locked=True),
        "system_settings": _perm(False, False, False, locked=True),
    },
    "brand_oem": {
        "work_orders":     _perm(True, False, False),
        "technicians":     _perm(True, False, False),
        "customers":       _perm(True, False, False),
        "accounting":      _perm(False, False, False),
        "invoices":        _perm(False, False, False),
        "refunds":         _perm(False, False, False),
        "inventory":       _perm(True, False, False),
        "warranty":        _perm(True, False, False),
        "disputes":        _perm(False, False, False),
        "audit_logs":      _perm(False, False, False, locked=True),
        "roles":           _perm(False, False, False, locked=True),
        "system_settings": _perm(False, False, False, locked=True),
    },
    "line_user": {
        # LINE 使用者進不到管理後台，全部封閉；此列僅為完整性。
        r: _perm(False, False, False, locked=True) for r in _RESOURCES
    },
}


_ROLE_META: dict[str, dict] = {
    "admin": {
        "name": "系統管理員",
        "description": "擁有完整系統管理權限；可管理所有業務資料",
    },
    "reviewer": {
        "name": "審核員",
        "description": "退款 / 保固 / 爭議審核；其餘為唯讀",
    },
    "technician": {
        "name": "技師",
        "description": "工單接受 / 完工 / 庫存查詢；無財務 / 角色管理權限",
    },
    "brand_oem": {
        "name": "品牌 OEM",
        "description": "品牌端唯讀視角：自家工單、客戶、庫存、保固",
    },
    "line_user": {
        "name": "LINE 使用者",
        "description": "終端消費者；不適用管理後台",
    },
}


def _role_to_dict(role_id: str, user_count: int) -> dict:
    meta = _ROLE_META[role_id]
    perms = _MATRIX.get(role_id, {})
    permissions = [
        {
            "resource": resource,
            **perms.get(resource, _perm(False, False, False, locked=True)),
        }
        for resource in _RESOURCES
    ]
    return {
        "id": role_id,
        "name": meta["name"],
        "description": meta["description"],
        "user_count": user_count,
        "is_system": True,
        "permissions": permissions,
    }


async def list_roles(*, tenant_id: str) -> list[dict]:
    """GET /roles — 5 系統角色 + 本租戶 user_count。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT role, COUNT(*) FROM users "
        "WHERE tenant_id = %s::uuid "
        "GROUP BY role",
        (tenant_id,),
    )
    rows = await cur.fetchall()
    counts = {str(r[0]): int(r[1] or 0) for r in rows}

    return [
        _role_to_dict(role_id, counts.get(role_id, 0))
        for role_id in _ROLE_META.keys()
    ]
