"""ADR-034 三庫使用者偏好服務。

資料依 principal owner 路由到 brand / technician / platform 權威庫；不建立跨庫
通用使用者資料庫。更新採 compare-and-set，並以 user action UUID 做 replay。
"""

from __future__ import annotations

import json
from typing import Any, Literal

import core.db as db_module
from core.errors import ApiError

PreferencePortal = Literal["brand", "tech", "platform"]

ZERO_SCOPE_ID = "00000000-0000-0000-0000-000000000000"
_MAX_VALUE_BYTES = 16 * 1024

# value_json 只容納已治理的跨裝置偏好；theme/locale/sidebar/command history/PWA
# 留在瀏覽器，不得透過本 API 偷渡。
_PREFERENCE_SHAPES: dict[PreferencePortal, dict[str, type]] = {
    "brand": {
        "saved_views": list,
        "table_columns": dict,
        "default_filters": dict,
        "notification_preferences": dict,
        "favorites": list,
    },
    "tech": {
        "workbench_sort": dict,
        "service_area_preferences": dict,
        "notification_preferences": dict,
        "recent_actions": list,
    },
    "platform": {
        "brand_view": dict,
        "governance_dashboard": dict,
    },
}

_SELECT_COLUMNS = (
    "id, portal, preference_key, value_json, version, last_action_id, updated_at"
)


def validate_preference(
    portal: PreferencePortal, preference_key: str, value: Any
) -> Any:
    shapes = _PREFERENCE_SHAPES.get(portal)
    expected = shapes.get(preference_key) if shapes else None
    if expected is None:
        raise ApiError(
            "PREFERENCE_KEY_NOT_ALLOWED",
            f"Preference key is not syncable for portal {portal}",
            422,
            [{"preference_key": preference_key, "portal": portal}],
        )
    if not isinstance(value, expected) or isinstance(value, (str, bytes)):
        raise ApiError(
            "PREFERENCE_SCHEMA_INVALID",
            f"Preference {preference_key} must be a {expected.__name__}",
            422,
            [{"preference_key": preference_key, "expected": expected.__name__}],
        )
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ApiError(
            "PREFERENCE_SCHEMA_INVALID",
            "Preference value must be valid JSON",
            422,
        )
    if len(encoded) > _MAX_VALUE_BYTES:
        raise ApiError(
            "PREFERENCE_TOO_LARGE",
            "Preference value exceeds 16 KiB",
            422,
            [{"max_bytes": _MAX_VALUE_BYTES, "actual_bytes": len(encoded)}],
        )
    return value


async def _connection_for(portal: PreferencePortal):
    try:
        if portal == "tech":
            return await db_module.require_tech_conn()
        if portal == "platform":
            return await db_module.require_platform_conn()
        if not await db_module._ensure_conn():
            raise RuntimeError("Brand DB unavailable")
        return db_module._conn
    except RuntimeError:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "portal": row[1],
        "preference_key": row[2],
        "value": row[3],
        "version": row[4],
        "last_action_id": str(row[5]),
        "updated_at": row[6].isoformat() if row[6] else None,
    }


async def list_preferences(
    *,
    portal: PreferencePortal,
    principal_id: str,
    scope_tenant_id: str,
) -> list[dict]:
    conn = await _connection_for(portal)
    cur = await conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM user_preferences "
        "WHERE principal_id = %s::uuid AND scope_tenant_id = %s::uuid "
        "AND portal = %s ORDER BY preference_key",
        (principal_id, scope_tenant_id, portal),
    )
    return [_row_to_dict(row) for row in await cur.fetchall()]


async def put_preference(
    *,
    portal: PreferencePortal,
    principal_id: str,
    scope_tenant_id: str,
    preference_key: str,
    value: Any,
    expected_version: int,
    action_id: str,
) -> dict:
    """以 CAS 更新；同 action_id replay 回目前結果且不增加 version。

    更新與建立皆用條件式 DML，避免「先 SELECT 再 UPDATE」的 check/use 競態：
    - UPDATE 只在 version 相符或 last_action_id 相同時成功。
    - create 只允許 expected_version=0，並以 ON CONFLICT DO NOTHING 擋併發雙建。
    - DML 無結果時重讀權威 row，回 machine-readable 409。
    """
    validate_preference(portal, preference_key, value)
    if expected_version < 0:
        raise ApiError("VALIDATION_ERROR", "expected_version must be >= 0", 422)

    conn = await _connection_for(portal)
    value_json = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )

    cur = await conn.execute(
        "UPDATE user_preferences SET "
        "value_json = CASE WHEN last_action_id = %s::uuid THEN value_json "
        "                  ELSE %s::jsonb END, "
        "version = CASE WHEN last_action_id = %s::uuid THEN version "
        "               ELSE version + 1 END, "
        "last_action_id = CASE WHEN last_action_id = %s::uuid THEN last_action_id "
        "                      ELSE %s::uuid END, "
        "updated_at = CASE WHEN last_action_id = %s::uuid THEN updated_at "
        "                  ELSE CURRENT_TIMESTAMP END "
        "WHERE principal_id = %s::uuid AND scope_tenant_id = %s::uuid "
        "AND portal = %s AND preference_key = %s "
        "AND (last_action_id = %s::uuid OR user_preferences.version = %s) "
        f"RETURNING {_SELECT_COLUMNS}",
        (
            action_id,
            value_json,
            action_id,
            action_id,
            action_id,
            action_id,
            principal_id,
            scope_tenant_id,
            portal,
            preference_key,
            action_id,
            expected_version,
        ),
    )
    row = await cur.fetchone()
    if row:
        return _row_to_dict(row)

    if expected_version == 0:
        cur = await conn.execute(
            "INSERT INTO user_preferences "
            "(principal_id, scope_tenant_id, portal, preference_key, value_json, "
            " version, last_action_id) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, 1, %s::uuid) "
            "ON CONFLICT (principal_id, scope_tenant_id, portal, preference_key) "
            "DO NOTHING "
            f"RETURNING {_SELECT_COLUMNS}",
            (
                principal_id,
                scope_tenant_id,
                portal,
                preference_key,
                value_json,
                action_id,
            ),
        )
        row = await cur.fetchone()
        if row:
            return _row_to_dict(row)

    cur = await conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM user_preferences "
        "WHERE principal_id = %s::uuid AND scope_tenant_id = %s::uuid "
        "AND portal = %s AND preference_key = %s",
        (principal_id, scope_tenant_id, portal, preference_key),
    )
    current_row = await cur.fetchone()
    current = _row_to_dict(current_row) if current_row else None
    raise ApiError(
        "CONCURRENT_MODIFICATION",
        "Preference version does not match current state",
        409,
        [
            {
                "preference_key": preference_key,
                "expected_version": expected_version,
                "current_version": current["version"] if current else 0,
                "current": current,
            }
        ],
    )
