"""ADR-036：hash-only service credential 與 aud/scope/tenant 負向測試。"""

from __future__ import annotations

import uuid
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.errors import ApiError
from services import service_credential_service as service

PEPPER = "test-only-pepper-that-is-longer-than-thirty-two-bytes"
SECRET = "a" * 43
PREFIX = "slksp_123456789abc"
PRINCIPAL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CREDENTIAL_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    async def fetchone(self):
        return self.row

    async def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, auth_row):
        self.auth_row = auth_row
        self.queries: list[tuple[str, tuple | None]] = []

    async def execute(self, query, params=None):
        self.queries.append((query, params))
        if "FROM service_credentials c" in query:
            return FakeCursor(row=self.auth_row)
        return FakeCursor()


def _row(**changes):
    values = {
        "credential_id": CREDENTIAL_ID,
        "secret_hash": service.hash_secret(SECRET, PEPPER),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=2),
        "revoked_at": None,
        "principal_id": PRINCIPAL_ID,
        "name": "line-gateway",
        "status": "active",
        "audiences": ["smartlock-internal-api"],
        "scopes": ["conversations:write"],
        "tenant_ids": [TENANT_ID],
        "allow_all_tenants": False,
    }
    values.update(changes)
    return tuple(values[key] for key in values)


@pytest.mark.unit
def test_hash_is_keyed_and_migration_has_no_plaintext_secret_column():
    digest = service.hash_secret(SECRET, PEPPER)
    assert len(digest) == 64
    assert SECRET not in digest
    migration = (
        Path(__file__).parents[2]
        / "SQL/migrations/121-service-principal-credentials.sql"
    ).read_text(encoding="utf-8")
    assert "secret_hash" in migration
    assert "created_action_id" in migration
    assert "plaintext_secret" not in migration
    assert not re.search(r"^\s*secret\s+", migration, flags=re.MULTILINE | re.IGNORECASE)


@pytest.mark.unit
def test_scope_wildcard_is_segment_bounded():
    assert service.scope_allows(["conversations:*"], "conversations:write")
    assert not service.scope_allows(["conversation:*"], "conversations:write")
    assert not service.scope_allows(["conversations:read"], "conversations:write")


@pytest.mark.unit
def test_management_rejects_naive_expiry_and_unbounded_grants():
    from pydantic import ValidationError

    from routers.platform_service_principals import PrincipalCreateBody

    with pytest.raises(ApiError) as raised:
        service._require_future_aware(
            datetime.now() + timedelta(days=1), "credential_expires_at"
        )
    assert raised.value.error_code == "VALIDATION_ERROR"

    with pytest.raises(ValidationError):
        PrincipalCreateBody(
            name="agent",
            audiences=["x" * 121],
            scopes=["conversations:write"],
            allowed_tenant_ids=[TENANT_ID],
            credential_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_authenticate_valid_credential(monkeypatch):
    conn = FakeConn(_row())
    monkeypatch.setenv("SERVICE_CREDENTIAL_PEPPER", PEPPER)

    async def fake_conn():
        return conn

    monkeypatch.setattr(service.db_module, "require_platform_conn", fake_conn)
    context = await service.authenticate(
        f"{PREFIX}.{SECRET}",
        audience="smartlock-internal-api",
        required_scope="conversations:write",
        request_id="req-1",
    )
    assert context.principal_id == str(PRINCIPAL_ID)
    service.assert_tenant_scope(context, str(TENANT_ID))
    assert any("last_used_at" in query for query, _ in conn.queries)
    assert any("service_auth_audit" in query for query, _ in conn.queries)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "audience", "scope", "error_code"),
    [
        ({"secret_hash": "0" * 64}, "smartlock-internal-api", "conversations:write", "SERVICE_AUTH_FAILED"),
        ({"revoked_at": datetime.now(timezone.utc)}, "smartlock-internal-api", "conversations:write", "SERVICE_CREDENTIAL_REVOKED"),
        ({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}, "smartlock-internal-api", "conversations:write", "SERVICE_CREDENTIAL_EXPIRED"),
        ({}, "wrong-audience", "conversations:write", "SERVICE_AUDIENCE_FORBIDDEN"),
        ({}, "smartlock-internal-api", "quotes:write", "SERVICE_SCOPE_FORBIDDEN"),
    ],
)
async def test_authentication_denies_invalid_lifecycle_or_grant(
    monkeypatch, changes, audience, scope, error_code
):
    conn = FakeConn(_row(**changes))
    monkeypatch.setenv("SERVICE_CREDENTIAL_PEPPER", PEPPER)

    async def fake_conn():
        return conn

    monkeypatch.setattr(service.db_module, "require_platform_conn", fake_conn)
    with pytest.raises(ApiError) as raised:
        await service.authenticate(
            f"{PREFIX}.{SECRET}",
            audience=audience,
            required_scope=scope,
            request_id="req-deny",
        )
    assert raised.value.error_code == error_code
    assert any("service_auth_audit" in query for query, _ in conn.queries)


@pytest.mark.unit
def test_tenant_grant_denies_cross_tenant():
    context = service.ServicePrincipalContext(
        principal_id=str(PRINCIPAL_ID),
        credential_id=str(CREDENTIAL_ID),
        name="line-gateway",
        scopes=frozenset({"conversations:write"}),
        audiences=frozenset({"smartlock-internal-api"}),
        allowed_tenant_ids=frozenset({str(TENANT_ID)}),
        allow_all_tenants=False,
    )
    with pytest.raises(ApiError) as raised:
        service.assert_tenant_scope(
            context, "00000000-0000-0000-0000-000000000002"
        )
    assert raised.value.error_code == "SERVICE_TENANT_FORBIDDEN"


@pytest.mark.unit
def test_management_routes_are_platform_scoped_and_idempotent():
    from routers.platform_service_principals import router

    routes = {route.path: route for route in router.routes}
    assert "/platform/service-principals" in routes
    assert "/platform/service-credentials/{credential_id}:rotate" in routes
    assert "/platform/service-credentials/{credential_id}:revoke" in routes
    source = Path(
        Path(__file__).parents[1] / "routers/platform_service_principals.py"
    ).read_text(encoding="utf-8")
    assert source.count('alias="Idempotency-Key"') == 3
    assert "overlap_seconds" in source


@pytest.mark.unit
def test_tech_ohs_caller_prefers_service_credential(monkeypatch):
    from services import work_order_service

    credential = f"{PREFIX}.{SECRET}"
    monkeypatch.setenv("TECH_API_SERVICE_CREDENTIAL", credential)
    monkeypatch.setenv("INTERNAL_API_TOKEN", "legacy-shared")
    value, headers = work_order_service._tech_service_auth()
    assert value == credential
    assert headers == {"X-Service-Credential": credential}
    assert "X-Internal-Token" not in headers
