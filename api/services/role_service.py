"""Roles 業務邏輯。

5 個系統角色（admin / reviewer / technician / brand_oem / line_user）為固定列表，
基準權限矩陣靜態定義；F-019 後可由 admin / tenant_admin 透過
`PATCH /api/v1/roles/{role_name}/permissions` 動態覆寫，覆寫值存於
`role_permissions` 表（SCD Type 1）。

list_roles 會將 _MATRIX 的預設值與 role_permissions 的覆寫合併後回傳。

user_count 由 SELECT role, COUNT(*) FROM users WHERE tenant_id=? GROUP BY role 計算。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.role_service")


# ─── F-019：階層強制 ─────────────────────────────────────────────
# Director > Manager > Other：actor 不能授權給「階層 >= 自己」的角色，
# 也不能授權自己沒有的權限（防止越權升級）。
ROLE_HIERARCHY: dict[str, int] = {
    "super_admin": 5,
    "tenant_admin": 4,
    "admin": 4,                  # admin 與 tenant_admin 同階（既有系統角色）
    "operations_director": 3,
    "operations_manager": 2,
    "reviewer": 2,
    "customer_service": 1,
    "support_agent": 1,
    "dispatch_officer": 1,
    "dispatcher": 1,
    "technician": 1,
    "brand_oem": 0,
    "auditor": 0,
    "line_user": 0,
}


def can_grant(actor_role: str, target_role: str) -> bool:
    """actor 是否能修改 target_role 的權限（階層必須嚴格 >）。"""
    return ROLE_HIERARCHY.get(actor_role, 0) > ROLE_HIERARCHY.get(target_role, 0)


# 允許執行 updateRolePermissions 的角色白名單（spec：admin / tenant_admin / super_admin）
RBAC_ADMIN_ROLES = frozenset({"admin", "tenant_admin", "super_admin"})

# 允許被修改的目標角色白名單（避免誤打 typo 角色名稱寫進 DB）
ALLOWED_TARGET_ROLES = frozenset(ROLE_HIERARCHY.keys())


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


_ACTIONS = ("read", "write", "delete")


def _flatten_matrix(role_id: str) -> set[str]:
    """把 _MATRIX[role_id] 攤平成 {`resource.action`} 集合（granted=True 的）。"""
    perms = _MATRIX.get(role_id, {})
    out: set[str] = set()
    for resource, p in perms.items():
        for action in _ACTIONS:
            if p.get(action):
                out.add(f"{resource}.{action}")
    return out


def _parse_permission_code(code: str) -> tuple[str, str]:
    """`resource.action` → (resource, action)；驗證 action 在白名單。"""
    if "." not in code:
        raise ApiError("VALIDATION_ERROR", f"invalid permission code: {code}", 422)
    resource, _, action = code.partition(".")
    if action not in _ACTIONS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unknown action `{action}` in `{code}` (must be read/write/delete)",
            422,
        )
    if resource not in _RESOURCES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unknown resource `{resource}` in `{code}`",
            422,
        )
    return resource, action


async def _load_overrides(*, tenant_id: str, role_name: str) -> dict[str, bool]:
    """從 role_permissions 表讀已覆寫的 permission_code → granted 映射。"""
    if not await _ensure_conn():
        return {}
    try:
        cur = await db_module._conn.execute(
            "SELECT permission_code, granted FROM role_permissions "
            "WHERE tenant_id = %s::uuid AND role_name = %s",
            (tenant_id, role_name),
        )
        return {str(r[0]): bool(r[1]) for r in await cur.fetchall()}
    except Exception as exc:  # noqa: BLE001 — 表可能尚未建立（新部署）
        logger.warning("role_permissions read failed (table missing?): %s", exc)
        return {}


def _apply_overrides(role_id: str, overrides: dict[str, bool]) -> set[str]:
    """以 overrides 覆寫 _MATRIX 預設權限，回傳最終 granted 集合。"""
    base = _flatten_matrix(role_id)
    for code, granted in overrides.items():
        if granted:
            base.add(code)
        else:
            base.discard(code)
    return base


async def list_roles(*, tenant_id: str) -> list[dict]:
    """GET /roles — 5 系統角色 + 本租戶 user_count + 動態 overrides 套用。"""
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

    roles: list[dict] = []
    for role_id in _ROLE_META.keys():
        base = _role_to_dict(role_id, counts.get(role_id, 0))
        overrides = await _load_overrides(tenant_id=tenant_id, role_name=role_id)
        if not overrides:
            roles.append(base)
            continue
        # 將 overrides 套用到 base.permissions
        for perm in base["permissions"]:
            resource = perm["resource"]
            for action in _ACTIONS:
                code = f"{resource}.{action}"
                if code in overrides and not perm.get("locked"):
                    perm[action] = overrides[code]
        roles.append(base)
    return roles


# ─── F-019：updateRolePermissions ────────────────────────────────


async def get_flat_permissions(
    *, tenant_id: str, role_name: str
) -> set[str]:
    """讀某角色當前實際擁有的扁平化 permission code 集合（含 overrides）。"""
    overrides = await _load_overrides(tenant_id=tenant_id, role_name=role_name)
    return _apply_overrides(role_name, overrides)


async def count_users_with_role(*, tenant_id: str, role_name: str) -> int:
    if not await _ensure_conn():
        return 0
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM users "
        "WHERE tenant_id = %s::uuid AND role = %s",
        (tenant_id, role_name),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 0


async def update_role_permissions(
    *,
    tenant_id: str,
    role_name: str,
    desired_permissions: list[str],
    actor_id: str,
    actor_role: str,
    reason: str,
) -> dict:
    """更新角色權限（差異 diff 寫 role_permissions），並廣播 WS。

    階層強制（PM Q2=A）：
      - actor 必須在 RBAC_ADMIN_ROLES（admin / tenant_admin / super_admin）
      - actor 不能修改階層 >= 自己的角色
      - actor 不能授權「自己沒有的 permission_code」（防止越權升級）

    Locked 權限（_MATRIX 中 locked=True）禁止透過 API 變更。

    回傳 dict 對齊 OpenAPI RolePermissionsUpdateResponse.data。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # ── 1. 角色合法性
    if role_name not in _ROLE_META:
        raise ApiError(
            "ROLE_NOT_FOUND",
            f"role `{role_name}` 不在系統角色清單",
            404,
        )
    if role_name not in ALLOWED_TARGET_ROLES:
        raise ApiError(
            "ROLE_NOT_FOUND",
            f"role `{role_name}` 不允許動態調整",
            404,
        )

    # ── 2. Actor RBAC：必須是 RBAC admin
    if actor_role not in RBAC_ADMIN_ROLES:
        raise ApiError(
            "FORBIDDEN",
            f"role `{actor_role}` 無權限調整 RBAC（需 admin / tenant_admin / super_admin）",
            403,
        )

    # ── 3. 階層強制
    if not can_grant(actor_role, role_name):
        raise ApiError(
            "RBAC_HIERARCHY_VIOLATION",
            f"角色 `{actor_role}` 階層不足以授權 `{role_name}`（actor 必須嚴格高於目標）",
            403,
        )

    # ── 4. 解析 + 驗證每個 code
    desired_set: set[str] = set()
    for code in desired_permissions:
        _parse_permission_code(code)  # 422 if invalid
        desired_set.add(code)

    # ── 5. Locked permission 禁止變更
    locked_codes: set[str] = set()
    for resource, perm in _MATRIX.get(role_name, {}).items():
        if perm.get("locked"):
            for action in _ACTIONS:
                locked_codes.add(f"{resource}.{action}")

    current_set = await get_flat_permissions(tenant_id=tenant_id, role_name=role_name)
    diff_codes = desired_set.symmetric_difference(current_set)
    locked_diff = diff_codes & locked_codes
    if locked_diff:
        raise ApiError(
            "PERMISSION_LOCKED",
            f"以下 permission 為系統強制鎖定，無法變更：{sorted(locked_diff)}",
            403,
        )

    # ── 6. 越權升級防護：actor 不能授權自己沒有的 code
    actor_perms = await get_flat_permissions(tenant_id=tenant_id, role_name=actor_role)
    granting = desired_set - current_set  # 新增的 grant
    out_of_scope = granting - actor_perms
    if out_of_scope and actor_role not in {"super_admin"}:
        # super_admin 可以授權任何系統內已知權限（但仍受 locked / 階層限制）
        raise ApiError(
            "RBAC_HIERARCHY_VIOLATION",
            f"actor 嘗試授權自己未持有的 permission：{sorted(out_of_scope)}",
            403,
        )

    # ── 7. 寫 role_permissions（UPSERT 對每個 code）
    now = datetime.now(timezone.utc)
    # 7a. 寫入「desired=True」的 code（granted=True）
    for code in desired_set:
        await db_module._conn.execute(
            "INSERT INTO role_permissions "
            "(tenant_id, role_name, permission_code, granted, updated_by, updated_at) "
            "VALUES (%s::uuid, %s, %s, TRUE, %s::uuid, %s) "
            "ON CONFLICT (tenant_id, role_name, permission_code) "
            "DO UPDATE SET granted = EXCLUDED.granted, "
            "              updated_by = EXCLUDED.updated_by, "
            "              updated_at = EXCLUDED.updated_at",
            (tenant_id, role_name, code, actor_id, now),
        )
    # 7b. 已存在但 desired 中沒有的 code → granted=FALSE（覆寫拒絕）
    revoking = current_set - desired_set
    for code in revoking:
        await db_module._conn.execute(
            "INSERT INTO role_permissions "
            "(tenant_id, role_name, permission_code, granted, updated_by, updated_at) "
            "VALUES (%s::uuid, %s, %s, FALSE, %s::uuid, %s) "
            "ON CONFLICT (tenant_id, role_name, permission_code) "
            "DO UPDATE SET granted = EXCLUDED.granted, "
            "              updated_by = EXCLUDED.updated_by, "
            "              updated_at = EXCLUDED.updated_at",
            (tenant_id, role_name, code, actor_id, now),
        )

    # ── 8. 統計受影響使用者
    affected = await count_users_with_role(
        tenant_id=tenant_id, role_name=role_name
    )

    # ── 9. WS publish + audit log（best-effort，不阻擋成功回應）
    ws_published = False
    try:
        from realtime.ws_hub import hub
        from uuid import uuid4

        event = {
            "type": "rbac.permission.changed",
            "payload": {
                "event_id": str(uuid4()),
                "event_type": "rbac.permission.changed",
                "event_time": now.isoformat(),
                "tenant_id": tenant_id,
                "version": 1,
                "actor": {"actor_type": "user", "actor_id": actor_id},
                "data": {
                    "role_id": role_name,
                    "changed_codes": sorted(diff_codes),
                    "granted_codes": sorted(granting),
                    "revoked_codes": sorted(revoking),
                    "affected_user_count": affected,
                },
            },
        }
        sent = await hub.publish("/realtime/rbac", event)
        ws_published = sent > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("rbac WS publish failed (non-fatal): %s", exc)

    try:
        from services import audit_log_service

        await audit_log_service.log_event(
            event_type="admin_action",
            actor_id=actor_id,
            actor_role=actor_role,
            action="role.permissions_updated",
            target_type="role",
            target_id=None,  # role_name 非 UUID，放 payload 即可
            payload={
                "role_name": role_name,
                "reason": reason,
                "before": sorted(current_set),
                "after": sorted(desired_set),
                "granted": sorted(granting),
                "revoked": sorted(revoking),
                "affected_user_count": affected,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("rbac audit log failed (non-fatal): %s", exc)

    return {
        "role_name": role_name,
        "permissions": sorted(desired_set),
        "updated_at": now.isoformat(),
        "ws_published": ws_published,
        "affected_user_count": affected,
    }
