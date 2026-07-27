"""ADR-036：服務主體與 hash-only credential 生命週期。"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import core.db as db_module
from core.errors import ApiError

_TOKEN_SEPARATOR = "."
_PREFIX_MARKER = "slksp_"


@dataclass(frozen=True)
class ServicePrincipalContext:
    principal_id: str
    credential_id: str
    name: str
    scopes: frozenset[str]
    audiences: frozenset[str]
    allowed_tenant_ids: frozenset[str]
    allow_all_tenants: bool
    legacy_fallback: bool = False


def _pepper() -> str:
    value = (os.getenv("SERVICE_CREDENTIAL_PEPPER") or "").strip()
    if len(value) < 32:
        raise ApiError(
            "SERVICE_CREDENTIALS_NOT_CONFIGURED",
            "SERVICE_CREDENTIAL_PEPPER must be at least 32 characters",
            503,
        )
    return value


def hash_secret(secret: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def parse_credential(value: str) -> tuple[str, str]:
    try:
        prefix, secret = value.strip().split(_TOKEN_SEPARATOR, 1)
    except ValueError as exc:
        raise ApiError("SERVICE_AUTH_FAILED", "Malformed service credential", 401) from exc
    if not prefix.startswith(_PREFIX_MARKER) or len(secret) < 32:
        raise ApiError("SERVICE_AUTH_FAILED", "Malformed service credential", 401)
    return prefix, secret


def scope_allows(grants: Iterable[str], required: str) -> bool:
    for grant in grants:
        if grant == "*" or grant == required:
            return True
        if grant.endswith(":*") and required.startswith(grant[:-1]):
            return True
    return False


def assert_tenant_scope(context: ServicePrincipalContext, tenant_id: str) -> None:
    try:
        normalized = str(uuid.UUID(str(tenant_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ApiError("SERVICE_TENANT_INVALID", "Invalid tenant scope", 422) from exc
    if not context.allow_all_tenants and normalized not in context.allowed_tenant_ids:
        raise ApiError(
            "SERVICE_TENANT_FORBIDDEN",
            "Service principal is not granted for this tenant",
            403,
        )


async def _audit(
    conn,
    *,
    principal_id: str | None,
    credential_id: str | None,
    prefix: str | None,
    event_type: str,
    outcome: str,
    request_id: str | None = None,
    audience: str | None = None,
    required_scope: str | None = None,
    tenant_id: str | None = None,
    detail: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO service_auth_audit (
            principal_id, credential_id, credential_prefix, event_type, outcome,
            request_id, audience, required_scope, tenant_id, detail_json
        ) VALUES (
            %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid,
            jsonb_build_object('detail', %s)
        )
        """,
        (
            principal_id,
            credential_id,
            prefix,
            event_type,
            outcome,
            request_id,
            audience,
            required_scope,
            tenant_id,
            detail or "",
        ),
    )


async def authenticate(
    raw_credential: str,
    *,
    audience: str,
    required_scope: str,
    request_id: str | None,
) -> ServicePrincipalContext:
    prefix, secret = parse_credential(raw_credential)
    try:
        conn = await db_module.require_platform_conn()
    except RuntimeError as exc:
        raise ApiError(
            "SERVICE_AUTH_UNAVAILABLE",
            "Service credential authority is unavailable",
            503,
        ) from exc
    cur = await conn.execute(
        """
        SELECT c.id, c.secret_hash, c.expires_at, c.revoked_at,
               p.id, p.name, p.status, p.audiences, p.scopes,
               p.allowed_tenant_ids, p.allow_all_tenants
          FROM service_credentials c
          JOIN service_principals p ON p.id = c.principal_id
         WHERE c.credential_prefix = %s
         LIMIT 1
        """,
        (prefix,),
    )
    row = await cur.fetchone()
    if not row:
        await _audit(
            conn,
            principal_id=None,
            credential_id=None,
            prefix=prefix,
            event_type="authenticate",
            outcome="denied",
            request_id=request_id,
            audience=audience,
            required_scope=required_scope,
            detail="unknown_prefix",
        )
        raise ApiError("SERVICE_AUTH_FAILED", "Invalid service credential", 401)

    (
        credential_id,
        expected_hash,
        expires_at,
        revoked_at,
        principal_id,
        name,
        status,
        audiences,
        scopes,
        tenant_ids,
        allow_all_tenants,
    ) = row
    supplied_hash = hash_secret(secret, _pepper())
    now = datetime.now(timezone.utc)
    denial: tuple[str, str, int] | None = None
    if not hmac.compare_digest(supplied_hash, str(expected_hash)):
        denial = ("SERVICE_AUTH_FAILED", "Invalid service credential", 401)
    elif status != "active":
        denial = ("SERVICE_PRINCIPAL_INACTIVE", "Service principal is inactive", 403)
    elif revoked_at is not None:
        denial = ("SERVICE_CREDENTIAL_REVOKED", "Service credential is revoked", 401)
    elif expires_at <= now:
        denial = ("SERVICE_CREDENTIAL_EXPIRED", "Service credential is expired", 401)
    elif audience not in set(audiences or ()):
        denial = ("SERVICE_AUDIENCE_FORBIDDEN", "Audience is not granted", 403)
    elif not scope_allows(scopes or (), required_scope):
        denial = ("SERVICE_SCOPE_FORBIDDEN", "Scope is not granted", 403)

    if denial:
        await _audit(
            conn,
            principal_id=str(principal_id),
            credential_id=str(credential_id),
            prefix=prefix,
            event_type="authenticate",
            outcome="denied",
            request_id=request_id,
            audience=audience,
            required_scope=required_scope,
            detail=denial[0],
        )
        raise ApiError(denial[0], denial[1], denial[2])

    await conn.execute(
        "UPDATE service_credentials SET last_used_at = CURRENT_TIMESTAMP WHERE id = %s::uuid",
        (credential_id,),
    )
    await _audit(
        conn,
        principal_id=str(principal_id),
        credential_id=str(credential_id),
        prefix=prefix,
        event_type="authenticate",
        outcome="success",
        request_id=request_id,
        audience=audience,
        required_scope=required_scope,
    )
    return ServicePrincipalContext(
        principal_id=str(principal_id),
        credential_id=str(credential_id),
        name=str(name),
        scopes=frozenset(scopes or ()),
        audiences=frozenset(audiences or ()),
        allowed_tenant_ids=frozenset(str(item) for item in (tenant_ids or ())),
        allow_all_tenants=bool(allow_all_tenants),
    )


def _new_plaintext() -> tuple[str, str, str]:
    prefix = f"{_PREFIX_MARKER}{secrets.token_hex(6)}"
    secret = secrets.token_urlsafe(32)
    return prefix, secret, f"{prefix}{_TOKEN_SEPARATOR}{secret}"


def _require_future_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field_name} must include an explicit timezone",
            422,
        )
    if value <= datetime.now(timezone.utc):
        raise ApiError("VALIDATION_ERROR", f"{field_name} must be in the future", 422)


async def create_principal(
    *,
    name: str,
    description: str | None,
    audiences: list[str],
    scopes: list[str],
    allowed_tenant_ids: list[str],
    allow_all_tenants: bool,
    expires_at: datetime,
    actor_id: str,
    action_id: str,
) -> dict:
    if not audiences or not scopes:
        raise ApiError("VALIDATION_ERROR", "audiences and scopes are required", 422)
    if not allow_all_tenants and not allowed_tenant_ids:
        raise ApiError(
            "VALIDATION_ERROR",
            "At least one tenant grant is required unless allow_all_tenants=true",
            422,
        )
    _require_future_aware(expires_at, "credential_expires_at")
    conn = await db_module.require_platform_conn()
    prefix, secret, plaintext = _new_plaintext()
    digest = hash_secret(secret, _pepper())
    async with conn.transaction():
        cur = await conn.execute(
            """
            INSERT INTO service_principals (
                name, description, audiences, scopes, allowed_tenant_ids,
                allow_all_tenants, created_by, created_action_id
            ) VALUES (%s, %s, %s, %s, %s::uuid[], %s, %s::uuid, %s::uuid)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                name,
                description,
                audiences,
                scopes,
                allowed_tenant_ids,
                allow_all_tenants,
                actor_id,
                action_id,
            ),
        )
        principal_row = await cur.fetchone()
        if not principal_row:
            cur = await conn.execute(
                "SELECT id FROM service_principals WHERE created_action_id = %s::uuid",
                (action_id,),
            )
            replay = await cur.fetchone()
            if replay:
                raise ApiError(
                    "IDEMPOTENCY_REPLAY_SECRET_UNAVAILABLE",
                    "Principal creation already completed; plaintext secret cannot be replayed",
                    409,
                )
            raise ApiError(
                "SERVICE_PRINCIPAL_NAME_CONFLICT",
                "Service principal name already exists",
                409,
            )
        principal_id = str(principal_row[0])
        cur = await conn.execute(
            """
            INSERT INTO service_credentials (
                principal_id, credential_prefix, secret_hash, expires_at,
                created_by, last_action_id
            ) VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s::uuid)
            RETURNING id
            """,
            (principal_id, prefix, digest, expires_at, actor_id, action_id),
        )
        credential_id = str((await cur.fetchone())[0])
        await _audit(
            conn,
            principal_id=principal_id,
            credential_id=credential_id,
            prefix=prefix,
            event_type="issue",
            outcome="success",
            request_id=action_id,
        )
    return {
        "principal_id": principal_id,
        "credential_id": credential_id,
        "credential": plaintext,
        "credential_prefix": prefix,
        "expires_at": expires_at,
        "secret_visible_once": True,
    }


async def list_principals() -> list[dict]:
    conn = await db_module.require_platform_conn()
    cur = await conn.execute(
        """
        SELECT p.id, p.name, p.description, p.status, p.audiences, p.scopes,
               p.allowed_tenant_ids, p.allow_all_tenants, p.created_at,
               count(c.id) FILTER (
                   WHERE c.revoked_at IS NULL AND c.expires_at > CURRENT_TIMESTAMP
               ) AS active_credentials
          FROM service_principals p
          LEFT JOIN service_credentials c ON c.principal_id = p.id
         GROUP BY p.id
         ORDER BY p.created_at DESC
        """
    )
    rows = await cur.fetchall()
    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "description": row[2],
            "status": row[3],
            "audiences": list(row[4] or ()),
            "scopes": list(row[5] or ()),
            "allowed_tenant_ids": [str(value) for value in (row[6] or ())],
            "allow_all_tenants": row[7],
            "created_at": row[8],
            "active_credentials": row[9],
        }
        for row in rows
    ]


async def revoke_credential(
    *, credential_id: str, reason: str, actor_id: str, action_id: str
) -> dict:
    conn = await db_module.require_platform_conn()
    async with conn.transaction():
        cur = await conn.execute(
            """
            UPDATE service_credentials
               SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP),
                   revoked_reason = COALESCE(revoked_reason, %s)
             WHERE id = %s::uuid
            RETURNING principal_id, credential_prefix, revoked_at
            """,
            (reason, credential_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", "Service credential not found", 404)
        await _audit(
            conn,
            principal_id=str(row[0]),
            credential_id=credential_id,
            prefix=row[1],
            event_type="revoke",
            outcome="success",
            request_id=action_id,
            detail=f"actor={actor_id}; reason={reason}",
        )
    return {"credential_id": credential_id, "revoked_at": row[2]}


async def rotate_credential(
    *,
    credential_id: str,
    expires_at: datetime,
    actor_id: str,
    action_id: str,
    overlap_seconds: int = 0,
) -> dict:
    _require_future_aware(expires_at, "expires_at")
    if overlap_seconds < 0 or overlap_seconds > 86400:
        raise ApiError(
            "VALIDATION_ERROR", "overlap_seconds must be between 0 and 86400", 422
        )
    conn = await db_module.require_platform_conn()
    prefix, secret, plaintext = _new_plaintext()
    digest = hash_secret(secret, _pepper())
    async with conn.transaction():
        cur = await conn.execute(
            """
            SELECT principal_id
              FROM service_credentials
             WHERE id = %s::uuid
               AND revoked_at IS NULL
               AND expires_at > CURRENT_TIMESTAMP
             FOR UPDATE
            """,
            (credential_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise ApiError("NOT_FOUND", "Active service credential not found", 404)
        principal_id = str(row[0])
        cur = await conn.execute(
            """
            INSERT INTO service_credentials (
                principal_id, credential_prefix, secret_hash, expires_at,
                rotated_from_id, created_by, last_action_id
            ) VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid)
            ON CONFLICT (principal_id, last_action_id) DO NOTHING
            RETURNING id
            """,
            (
                principal_id,
                prefix,
                digest,
                expires_at,
                credential_id,
                actor_id,
                action_id,
            ),
        )
        created = await cur.fetchone()
        if not created:
            raise ApiError(
                "IDEMPOTENCY_REPLAY_SECRET_UNAVAILABLE",
                "Rotation already completed; plaintext secret cannot be replayed",
                409,
            )
        new_id = str(created[0])
        if overlap_seconds:
            await conn.execute(
                """
                UPDATE service_credentials
                   SET expires_at = LEAST(
                       expires_at,
                       CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                   ),
                       revoked_reason = 'rotation overlap'
                 WHERE id = %s::uuid
                """,
                (overlap_seconds, credential_id),
            )
        else:
            await conn.execute(
                """
                UPDATE service_credentials
                   SET revoked_at = CURRENT_TIMESTAMP,
                       revoked_reason = 'rotated'
                 WHERE id = %s::uuid
                """,
                (credential_id,),
            )
        await _audit(
            conn,
            principal_id=principal_id,
            credential_id=new_id,
            prefix=prefix,
            event_type="rotate",
            outcome="success",
            request_id=action_id,
            detail=(
                f"rotated_from={credential_id}; overlap_seconds={overlap_seconds}"
            ),
        )
    return {
        "principal_id": principal_id,
        "credential_id": new_id,
        "credential": plaintext,
        "credential_prefix": prefix,
        "expires_at": expires_at,
        "secret_visible_once": True,
        "rotated_from_id": credential_id,
        "overlap_seconds": overlap_seconds,
    }
