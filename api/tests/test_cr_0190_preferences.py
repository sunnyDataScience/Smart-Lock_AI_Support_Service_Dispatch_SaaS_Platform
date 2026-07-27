"""CR-0190 / ADR-034：三庫偏好、allowlist、CAS 409 與路由守衛。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.errors import ApiError
from services import preference_service

pytestmark = pytest.mark.unit

TENANT_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
ACTION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class _FakeCur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    async def fetchone(self):
        return self._row

    async def fetchall(self):
        return self._rows


def _row(*, version=1, action_id=ACTION_ID, value=None):
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return (
        uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "brand",
        "saved_views",
        value if value is not None else [{"name": "待派工"}],
        version,
        uuid.UUID(action_id),
        now,
    )


class _FakeConn:
    def __init__(self, *, upsert_row=None, current_row=None, rows=None):
        self.upsert_row = upsert_row
        self.current_row = current_row
        self.rows = rows or []
        self.calls: list[tuple[str, object]] = []

    async def execute(self, sql, args=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, args))
        if normalized.startswith("UPDATE user_preferences"):
            return _FakeCur(row=self.upsert_row)
        if normalized.startswith("INSERT INTO user_preferences"):
            return _FakeCur(row=self.upsert_row)
        if "FROM user_preferences" in normalized and "preference_key = %s" in normalized:
            return _FakeCur(row=self.current_row)
        return _FakeCur(rows=self.rows)


@pytest.mark.parametrize(
    ("portal", "key", "value"),
    [
        ("brand", "saved_views", [{"name": "待派工"}]),
        ("brand", "table_columns", {"work_orders": ["number", "status"]}),
        ("tech", "workbench_sort", {"by": "distance", "direction": "asc"}),
        ("platform", "governance_dashboard", {"range": "7d"}),
    ],
)
def test_preference_allowlist_accepts_known_shape(portal, key, value):
    assert preference_service.validate_preference(portal, key, value) == value


@pytest.mark.parametrize(
    ("portal", "key", "value"),
    [
        ("brand", "theme", "dark"),
        ("brand", "saved_views", {"wrong": "shape"}),
        ("tech", "service_area_preferences", []),
        ("platform", "unknown", {}),
    ],
)
def test_preference_allowlist_rejects_unknown_or_wrong_shape(portal, key, value):
    with pytest.raises(ApiError) as exc:
        preference_service.validate_preference(portal, key, value)
    assert exc.value.status_code == 422


def test_preference_payload_has_16kib_limit():
    with pytest.raises(ApiError) as exc:
        preference_service.validate_preference(
            "brand", "default_filters", {"query": "x" * 17000}
        )
    assert exc.value.error_code == "PREFERENCE_TOO_LARGE"


@pytest.mark.asyncio
async def test_put_uses_atomic_cas_and_returns_version(monkeypatch):
    conn = _FakeConn(upsert_row=_row(version=3))

    async def _brand_conn(_portal):
        return conn

    monkeypatch.setattr(preference_service, "_connection_for", _brand_conn)
    result = await preference_service.put_preference(
        portal="brand",
        principal_id=USER_ID,
        scope_tenant_id=TENANT_ID,
        preference_key="saved_views",
        value=[{"name": "待派工"}],
        expected_version=2,
        action_id=ACTION_ID,
    )

    assert result["version"] == 3
    sql = conn.calls[0][0]
    assert sql.startswith("UPDATE user_preferences")
    assert "last_action_id" in sql
    assert "user_preferences.version = %s" in sql


@pytest.mark.asyncio
async def test_stale_version_returns_machine_readable_409(monkeypatch):
    current = _row(version=7, action_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    conn = _FakeConn(upsert_row=None, current_row=current)

    async def _brand_conn(_portal):
        return conn

    monkeypatch.setattr(preference_service, "_connection_for", _brand_conn)
    with pytest.raises(ApiError) as exc:
        await preference_service.put_preference(
            portal="brand",
            principal_id=USER_ID,
            scope_tenant_id=TENANT_ID,
            preference_key="saved_views",
            value=[],
            expected_version=2,
            action_id=ACTION_ID,
        )

    assert exc.value.status_code == 409
    assert exc.value.error_code == "CONCURRENT_MODIFICATION"
    assert exc.value.details[0]["current_version"] == 7
    assert exc.value.details[0]["current"]["version"] == 7


@pytest.mark.asyncio
async def test_brand_cross_tenant_is_denied_before_service(
    client, admin_headers, monkeypatch
):
    async def _must_not_call(**_kwargs):
        raise AssertionError("跨租戶不得進 service")

    monkeypatch.setattr(preference_service, "list_preferences", _must_not_call)
    other = "00000000-0000-0000-0000-000000000099"
    response = await client.get(
        f"/tenants/{other}/me/preferences",
        headers=admin_headers,
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_preference_write_requires_action_id(client, admin_headers):
    response = await client.put(
        f"/tenants/{TENANT_ID}/me/preferences/saved_views",
        headers=admin_headers,
        json={"value": [], "expected_version": 0},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.asyncio
async def test_platform_endpoint_rejects_brand_token(client, admin_headers):
    response = await client.get(
        "/api/v2/platform/me/preferences",
        headers=admin_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_brand_preference_route_passes_authority_scope(
    client, admin_headers, monkeypatch
):
    captured = {}

    async def _put(**kwargs):
        captured.update(kwargs)
        return {
            "preference_key": kwargs["preference_key"],
            "value": kwargs["value"],
            "version": 1,
            "last_action_id": kwargs["action_id"],
            "updated_at": "2026-07-27T00:00:00+00:00",
        }

    monkeypatch.setattr(preference_service, "put_preference", _put)
    response = await client.put(
        f"/tenants/{TENANT_ID}/me/preferences/saved_views",
        headers={**admin_headers, "Idempotency-Key": ACTION_ID},
        json={"value": [{"name": "我的檢視"}], "expected_version": 0},
    )
    assert response.status_code == 200
    assert captured["portal"] == "brand"
    assert captured["scope_tenant_id"] == TENANT_ID
    assert captured["principal_id"] == USER_ID


def test_migration_is_routed_to_all_authority_databases():
    migration = (
        Path(__file__).parents[2] / "SQL/migrations/120-user-preferences.sql"
    ).read_text(encoding="utf-8")
    assert "-- migrate-targets: brand,tech,platform" in migration
    assert "UNIQUE (principal_id, scope_tenant_id, portal, preference_key)" in migration
    assert "octet_length(value_json::text) <= 16384" in migration
