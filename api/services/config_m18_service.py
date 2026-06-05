"""M18 Runtime Config Governance service (ADR-0067 Phase 0 / CR-0004 §8).

架構：4 saas 表（config_namespace / config_version / config_rollout / config_audit）
     + in-process TTL 30s cache for ACL read（HD-05：no Redis/NATS）。

MVP 邊界（Phase 0 完整實作）：
  - draft（schema 驗 + audit）
  - instant rollout（即啟用、dethrone 前一 active）
  - canary rollout：建 config_rollout 記錄 + stage='5%' + next_stage_eta，
    readConfig 保守回前一 active 版本（rolling_out 期間不服務未完成版本）
  - rollback（重啟 parent_version_id）
  - SoD dual-sign（X-Initiator / X-Approver 相異）
  - config_audit append-only
  - ACL read（404/409 + TTL 30s cache + cache:hit|miss）
  - version snapshot

Phase II deferred（需 scheduler，標 logger.info DEFERRED）：
  - canary 自動 stage 推進（5%→50%→100%）
  - SLO 自動 halt

相依：core.db._conn（autocommit psycopg3），services.config_service 不動。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.config_m18_service")

# ─────────────────────────────────────────────────────────────────────────────
# In-process TTL cache（HD-05：no Redis）
# key = (tenant_id, namespace, key_name)
# value = {"value": ..., "version_id": ..., "resolved_at": ...}
# ─────────────────────────────────────────────────────────────────────────────
_READ_CACHE: dict[tuple[str | None, str, str], dict] = {}
_CACHE_TTL_SECONDS = 30


def _cache_key(tenant_id: str | None, namespace: str, key: str) -> tuple:
    return (tenant_id, namespace, key)


def _cache_get(
    tenant_id: str | None, namespace: str, key: str
) -> dict | None:
    entry = _READ_CACHE.get(_cache_key(tenant_id, namespace, key))
    if not entry:
        return None
    if time.monotonic() - entry["_cached_at"] > _CACHE_TTL_SECONDS:
        del _READ_CACHE[_cache_key(tenant_id, namespace, key)]
        return None
    return entry


def _cache_put(
    tenant_id: str | None, namespace: str, key: str, value: Any,
    version_id: str, resolved_at: str
) -> None:
    _READ_CACHE[_cache_key(tenant_id, namespace, key)] = {
        "value": value,
        "version_id": version_id,
        "resolved_at": resolved_at,
        "_cached_at": time.monotonic(),
    }


def _cache_invalidate(tenant_id: str | None, namespace: str, key: str) -> None:
    _READ_CACHE.pop(_cache_key(tenant_id, namespace, key), None)


# ─────────────────────────────────────────────────────────────────────────────
# JSON Schema validation（HD-03 pre-flight）
# ─────────────────────────────────────────────────────────────────────────────

def _validate_against_schema(proposed_value: Any, json_schema: dict) -> None:
    """Validate proposed_value against json_schema.

    Raises ApiError CONFIG_SCHEMA_INVALID (422) on failure.
    Uses jsonschema library if available; falls back to minimal type check.
    """
    try:
        import jsonschema  # type: ignore[import]
        try:
            jsonschema.validate(instance=proposed_value, schema=json_schema)
        except jsonschema.ValidationError as exc:
            raise ApiError(
                "CONFIG_SCHEMA_INVALID",
                f"proposed_value 不符合 namespace schema: {exc.message}",
                422,
            )
    except ImportError:
        # Fallback: 只確認 schema type=object 時 value 是 dict
        if json_schema.get("type") == "object" and not isinstance(proposed_value, dict):
            raise ApiError(
                "CONFIG_SCHEMA_INVALID",
                "proposed_value 必須是 object（namespace schema 要求）",
                422,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_namespace_schema(namespace: str) -> dict:
    """Fetch json_schema for a namespace. Raises 404 if namespace not found."""
    cur = await db_module._conn.execute(
        "SELECT json_schema FROM saas.config_namespace WHERE code = %s",
        (namespace,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CONFIG_NOT_FOUND", f"namespace '{namespace}' 不存在", 404)
    return row[0]


async def _append_audit(
    *,
    tenant_id: str | None,
    config_version_id: str,
    actor_user_id: str,
    action: str,
    diff: dict | None,
) -> None:
    """Append a record to saas.config_audit (append-only)."""
    await db_module._conn.execute(
        """
        INSERT INTO saas.config_audit
            (tenant_id, config_version_id, actor_user_id, action, diff)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
        """,
        (
            tenant_id,
            config_version_id,
            actor_user_id,
            action,
            json.dumps(diff) if diff is not None else None,
        ),
    )


async def _dethrone_active(
    tenant_id: str | None, namespace: str, key: str
) -> str | None:
    """Set the current 'active' version to 'retired'. Returns dethroned version_id or None."""
    cur = await db_module._conn.execute(
        """
        UPDATE saas.config_version
        SET state = 'retired'
        WHERE tenant_id IS NOT DISTINCT FROM %s::uuid
          AND namespace = %s
          AND key = %s
          AND state = 'active'
        RETURNING id
        """,
        (tenant_id, namespace, key),
    )
    row = await cur.fetchone()
    return str(row[0]) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def list_namespaces(
    tenant_id: str, namespace_filter: str | None = None
) -> list[str]:
    """List config_namespace.code values. Optional namespace filter (exact match)."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if namespace_filter:
        cur = await db_module._conn.execute(
            "SELECT code FROM saas.config_namespace WHERE code = %s ORDER BY code",
            (namespace_filter,),
        )
    else:
        cur = await db_module._conn.execute(
            "SELECT code FROM saas.config_namespace ORDER BY code"
        )
    rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_active_version(
    tenant_id: str, namespace: str, key: str
) -> dict:
    """Get the active config_version for (tenant, namespace, key).

    Returns dict with active_version_id (None if no active) + active_value + active_since.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        """
        SELECT id, value, activated_at
        FROM saas.config_version
        WHERE tenant_id IS NOT DISTINCT FROM %s::uuid
          AND namespace = %s
          AND key = %s
          AND state = 'active'
        """,
        (tenant_id, namespace, key),
    )
    row = await cur.fetchone()
    if not row:
        return {
            "namespace": namespace,
            "key": key,
            "active_version_id": None,
            "active_value": None,
            "active_since": None,
        }
    return {
        "namespace": namespace,
        "key": key,
        "active_version_id": str(row[0]),
        "active_value": row[1],
        "active_since": row[2].isoformat() if row[2] else None,
    }


async def create_draft(
    *,
    tenant_id: str,
    namespace: str,
    key: str,
    proposed_value: Any,
    reason: str,
    change_request_id: str | None,
    initiator_user_id: str,
) -> dict:
    """Create a config_version in state='draft'. Validates against namespace json_schema.

    Returns dict: version_id, state, created_at.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # Fetch and validate schema
    schema = await _get_namespace_schema(namespace)
    _validate_against_schema(proposed_value, schema)

    cur = await db_module._conn.execute(
        """
        INSERT INTO saas.config_version
            (tenant_id, namespace, key, value, state, created_by)
        VALUES (%s::uuid, %s, %s, %s::jsonb, 'draft', %s::uuid)
        RETURNING id, state, created_at
        """,
        (tenant_id, namespace, key, json.dumps(proposed_value), initiator_user_id),
    )
    row = await cur.fetchone()
    version_id = str(row[0])
    state = row[1]
    created_at = row[2].isoformat()

    await _append_audit(
        tenant_id=tenant_id,
        config_version_id=version_id,
        actor_user_id=initiator_user_id,
        action="draft_created",
        diff={
            "proposed_value": proposed_value,
            "reason": reason,
            "change_request_id": change_request_id,
        },
    )

    return {"version_id": version_id, "state": state, "created_at": created_at}


async def start_rollout(
    *,
    tenant_id: str,
    namespace: str,
    key: str,
    version_id: str,
    strategy: str,
    observation_minutes: int,
    initiator_user_id: str,
    approver_user_id: str,
) -> dict:
    """Start a rollout for a draft config_version.

    strategy='instant': immediately activate, dethrone previous active.
    strategy='canary_5_50_100': set state='rolling_out', stage='5%', next_stage_eta.
      NOTE: readConfig returns previous active during rolling_out (conservative).
      Auto stage-advance (5%→50%→100%) and SLO halt are Phase II (needs scheduler).

    Returns: rollout_id, version_id, current_stage, next_stage_eta.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if strategy not in ("canary_5_50_100", "instant"):
        raise ApiError("VALIDATION_ERROR", "strategy 必須為 canary_5_50_100 或 instant", 422)

    # Clamp observation_minutes ≥ 10 (HD-01 hard floor)
    if observation_minutes < 10:
        logger.info(
            "[config_m18] observation_minutes %d < 10 → clamped to 10 (HD-01 hard floor)",
            observation_minutes,
        )
        observation_minutes = 10

    # Fetch and validate version belongs to this tenant/namespace/key and is 'draft'
    cur = await db_module._conn.execute(
        """
        SELECT id, state, namespace, key, tenant_id, parent_version_id
        FROM saas.config_version
        WHERE id = %s::uuid
        """,
        (version_id,),
    )
    ver = await cur.fetchone()
    if not ver:
        raise ApiError("CONFIG_NOT_FOUND", f"version {version_id} 不存在", 404)
    if ver[1] != "draft":
        raise ApiError("CONFLICT", f"version state='{ver[1]}' 不可 rollout（需 draft）", 409)
    if ver[2] != namespace or ver[3] != key:
        raise ApiError("VALIDATION_ERROR", "version namespace/key 與 path 不符", 422)

    now = datetime.now(timezone.utc)

    if strategy == "instant":
        # Dethrone previous active（→ retired）; 記其 id 作為本版 parent，
        # 讓 rollback 能重啟前一版（ADR-0067 rollback ≤ 1min RTO restore previous）。
        dethroned_id = await _dethrone_active(tenant_id, namespace, key)

        # Activate this version；parent_version_id 指向被 dethrone 的前一 active
        # （COALESCE：不覆寫既有 parent；首版無前任時保持 NULL）。
        await db_module._conn.execute(
            """
            UPDATE saas.config_version
            SET state = 'active',
                activated_at = %s,
                parent_version_id = COALESCE(parent_version_id, %s::uuid)
            WHERE id = %s::uuid
            """,
            (now, dethroned_id, version_id),
        )

        # Create rollout record with stage='100%'
        instant_stage = "100%"
        cur = await db_module._conn.execute(
            """
            INSERT INTO saas.config_rollout
                (config_version_id, strategy, current_stage, stage_started_at,
                 next_stage_eta, initiator_user_id, approver_user_id)
            VALUES (%s::uuid, 'instant', %s, %s, NULL, %s::uuid, %s::uuid)
            RETURNING id
            """,
            (version_id, instant_stage, now, initiator_user_id, approver_user_id),
        )
        rollout_row = await cur.fetchone()
        rollout_id = str(rollout_row[0])

        # Audit: rollout_started + activated
        await _append_audit(
            tenant_id=tenant_id,
            config_version_id=version_id,
            actor_user_id=initiator_user_id,
            action="rollout_started",
            diff={"strategy": "instant", "approver": approver_user_id},
        )
        await _append_audit(
            tenant_id=tenant_id,
            config_version_id=version_id,
            actor_user_id=approver_user_id,
            action="activated",
            diff={"rollout_id": rollout_id},
        )

        # Invalidate ACL read cache
        _cache_invalidate(tenant_id, namespace, key)

        return {
            "rollout_id": rollout_id,
            "version_id": version_id,
            "current_stage": "100%",
            "next_stage_eta": None,
        }

    else:  # canary_5_50_100
        next_stage_eta = now + timedelta(minutes=observation_minutes)

        # Set version to rolling_out (NOT yet active — conservative)
        await db_module._conn.execute(
            """
            UPDATE saas.config_version
            SET state = 'rolling_out'
            WHERE id = %s::uuid
            """,
            (version_id,),
        )

        canary_stage = "5%"
        cur = await db_module._conn.execute(
            """
            INSERT INTO saas.config_rollout
                (config_version_id, strategy, current_stage, stage_started_at,
                 next_stage_eta, initiator_user_id, approver_user_id)
            VALUES (%s::uuid, 'canary_5_50_100', %s, %s, %s, %s::uuid, %s::uuid)
            RETURNING id
            """,
            (version_id, canary_stage, now, next_stage_eta, initiator_user_id, approver_user_id),
        )
        rollout_row = await cur.fetchone()
        rollout_id = str(rollout_row[0])

        await _append_audit(
            tenant_id=tenant_id,
            config_version_id=version_id,
            actor_user_id=initiator_user_id,
            action="rollout_started",
            diff={
                "strategy": "canary_5_50_100",
                "approver": approver_user_id,
                "current_stage": "5%",
                "next_stage_eta": next_stage_eta.isoformat(),
                "observation_minutes": observation_minutes,
            },
        )

        # Phase II deferred log (MUST NOT be silent per spec)
        logger.info(
            "[config_m18] DEFERRED (Phase II): canary stage auto-advance (5%%->50%%->100%%) "
            "and SLO halt require a scheduler. rollout_id=%s version_id=%s "
            "next_stage_eta=%s — integrate with cron/scheduler in Phase II.",
            rollout_id, version_id, next_stage_eta.isoformat(),
        )

        return {
            "rollout_id": rollout_id,
            "version_id": version_id,
            "current_stage": "5%",
            "next_stage_eta": next_stage_eta.isoformat(),
        }


async def rollback(
    *,
    tenant_id: str,
    rollout_id: str,
    actor_user_id: str,
) -> dict:
    """Rollback a rollout: set version rolled_back, re-activate parent_version if exists.

    Returns: rollout_id, version_id, current_stage, next_stage_eta.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        """
        SELECT r.id, r.config_version_id, r.current_stage,
               v.tenant_id, v.namespace, v.key, v.parent_version_id
        FROM saas.config_rollout r
        JOIN saas.config_version v ON v.id = r.config_version_id
        WHERE r.id = %s::uuid
        """,
        (rollout_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CONFIG_NOT_FOUND", f"rollout {rollout_id} 不存在", 404)

    _rid, version_id, current_stage, ver_tenant, namespace, key, parent_vid = row
    version_id_str = str(version_id)
    parent_vid_str = str(parent_vid) if parent_vid else None

    if current_stage == "rolled_back":
        raise ApiError("CONFLICT", "rollout 已 rolled_back，無法再次 rollback", 409)

    # Mark rollout as rolled_back
    await db_module._conn.execute(
        "UPDATE saas.config_rollout SET current_stage = 'rolled_back' WHERE id = %s::uuid",
        (rollout_id,),
    )

    # Mark version as rolled_back
    await db_module._conn.execute(
        "UPDATE saas.config_version SET state = 'rolled_back' WHERE id = %s::uuid",
        (version_id,),
    )

    # Re-activate parent_version if exists
    if parent_vid_str:
        now = datetime.now(timezone.utc)
        await db_module._conn.execute(
            """
            UPDATE saas.config_version
            SET state = 'active', activated_at = %s
            WHERE id = %s::uuid AND state IN ('retired','rolled_back')
            """,
            (now, parent_vid_str),
        )

    await _append_audit(
        tenant_id=str(ver_tenant) if ver_tenant else None,
        config_version_id=version_id_str,
        actor_user_id=actor_user_id,
        action="rolled_back",
        diff={
            "rollout_id": rollout_id,
            "parent_version_id": parent_vid_str,
            "re_activated_parent": parent_vid_str is not None,
        },
    )

    # Invalidate cache
    _cache_invalidate(str(ver_tenant) if ver_tenant else None, namespace, key)

    return {
        "rollout_id": rollout_id,
        "version_id": version_id_str,
        "current_stage": "rolled_back",
        "next_stage_eta": None,
    }


async def read_config_acl(
    *,
    tenant_id: str,
    namespace: str,
    key: str,
    requested_version_id: str | None = None,
) -> dict:
    """ACL read — GET /m18/config-read/{namespace}/{key}.

    Returns: namespace, key, value, version_id, resolved_at, cache (hit|miss).
    Response header X-Config-Version = version_id (set by router).

    Rules:
    - No active version → 404 CONFIG_NOT_FOUND
    - active version exists but ?version != active version_id → 409 CONFIG_VERSION_MISMATCH
    - in-process TTL 30s cache; cache:hit if served from cache, cache:miss on DB read

    Conservative during canary: rolling_out version is NOT served; only active is served.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # Try cache
    cached = _cache_get(tenant_id, namespace, key)
    if cached:
        hit_version_id = cached["version_id"]
        if requested_version_id and requested_version_id != hit_version_id:
            raise ApiError(
                "CONFIG_VERSION_MISMATCH",
                f"requested version {requested_version_id} != 現行 active {hit_version_id} "
                f"(ADR-0068 per-transaction snapshot)",
                409,
            )
        return {
            "namespace": namespace,
            "key": key,
            "value": cached["value"],
            "version_id": hit_version_id,
            "resolved_at": cached["resolved_at"],
            "cache": "hit",
        }

    # DB read
    cur = await db_module._conn.execute(
        """
        SELECT id, value, activated_at
        FROM saas.config_version
        WHERE tenant_id IS NOT DISTINCT FROM %s::uuid
          AND namespace = %s
          AND key = %s
          AND state = 'active'
        """,
        (tenant_id, namespace, key),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CONFIG_NOT_FOUND", f"({namespace}/{key}) 無 active version", 404)

    db_version_id = str(row[0])
    value = row[1]
    resolved_at = (row[2] or datetime.now(timezone.utc)).isoformat()

    if requested_version_id and requested_version_id != db_version_id:
        raise ApiError(
            "CONFIG_VERSION_MISMATCH",
            f"requested version {requested_version_id} != active version {db_version_id} "
            f"(ADR-0068 per-transaction snapshot)",
            409,
        )

    # Populate cache
    _cache_put(tenant_id, namespace, key, value, db_version_id, resolved_at)

    return {
        "namespace": namespace,
        "key": key,
        "value": value,
        "version_id": db_version_id,
        "resolved_at": resolved_at,
        "cache": "miss",
    }


async def list_audit(
    *,
    tenant_id: str,
    namespace: str,
    key: str,
    cursor: str | None = None,
    limit: int = 20,
) -> dict:
    """List config_audit for (tenant, namespace, key), cursor-paginated by audit.id DESC.

    cursor = last seen audit id (bigint as string).
    Returns: items list + next_cursor.
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    limit = min(max(limit, 1), 100)

    if cursor:
        try:
            cursor_id = int(cursor)
        except ValueError:
            raise ApiError("VALIDATION_ERROR", "cursor 格式錯誤（應為整數）", 422)
        cur = await db_module._conn.execute(
            """
            SELECT ca.id, ca.config_version_id, ca.actor_user_id,
                   ca.action, ca.diff, ca.ts
            FROM saas.config_audit ca
            JOIN saas.config_version cv ON cv.id = ca.config_version_id
            WHERE (ca.tenant_id IS NOT DISTINCT FROM %s::uuid
                   OR cv.tenant_id IS NOT DISTINCT FROM %s::uuid)
              AND cv.namespace = %s
              AND cv.key = %s
              AND ca.id < %s
            ORDER BY ca.id DESC
            LIMIT %s
            """,
            (tenant_id, tenant_id, namespace, key, cursor_id, limit + 1),
        )
    else:
        cur = await db_module._conn.execute(
            """
            SELECT ca.id, ca.config_version_id, ca.actor_user_id,
                   ca.action, ca.diff, ca.ts
            FROM saas.config_audit ca
            JOIN saas.config_version cv ON cv.id = ca.config_version_id
            WHERE (ca.tenant_id IS NOT DISTINCT FROM %s::uuid
                   OR cv.tenant_id IS NOT DISTINCT FROM %s::uuid)
              AND cv.namespace = %s
              AND cv.key = %s
            ORDER BY ca.id DESC
            LIMIT %s
            """,
            (tenant_id, tenant_id, namespace, key, limit + 1),
        )

    rows = await cur.fetchall()
    has_more = len(rows) > limit
    items_raw = rows[:limit]

    items = []
    for r in items_raw:
        diff = r[4]
        reason = None
        if isinstance(diff, dict):
            reason = diff.get("reason")
        items.append({
            "id": r[0],
            "version_id": str(r[1]),
            "actor": str(r[2]),
            "action": r[3],
            "ts": r[5].isoformat(),
            "diff": diff,
            "reason": reason,
        })

    next_cursor = str(items_raw[-1][0]) if has_more and items_raw else None
    return {"items": items, "next_cursor": next_cursor}


# ─────────────────────────────────────────────────────────────────────────────
# Phase II placeholder — canary stage advance helper (not wired to cron)
# ─────────────────────────────────────────────────────────────────────────────

async def _advance_canary_stage(rollout_id: str) -> dict:
    """Advance one canary rollout: 5%→50%→100%+activate。

    cron 接入：`api/realtime/config_canary_advance_cron.py` 每 5 分鐘掃所有
    `current_stage IN ('5%','50%') AND next_stage_eta < NOW` 的 rollout 呼此函式。

    流程：
      - 5% → 50%：UPDATE rollout SET current_stage='50%' + stage_started_at=NOW
        + next_stage_eta=NOW+(原 observation duration)；audit stage_advanced
      - 50% → 100%：UPDATE rollout SET current_stage='100%' + next_stage_eta=NULL
        + _dethrone_active 舊版 + UPDATE config_version state='active'；
        audit stage_advanced + activated；cache invalidate

    Returns: {rollout_id, version_id, new_stage, next_stage_eta}
    """
    cur = await db_module._conn.execute(
        """
        SELECT cr.id, cr.config_version_id, cr.current_stage,
               cr.stage_started_at, cr.next_stage_eta,
               cv.tenant_id, cv.namespace, cv.key,
               cr.initiator_user_id, cr.approver_user_id
        FROM saas.config_rollout cr
        JOIN saas.config_version cv ON cv.id = cr.config_version_id
        WHERE cr.id = %s::uuid
        """,
        (rollout_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CONFIG_NOT_FOUND", f"rollout {rollout_id} 不存在", 404)
    (
        _, version_id, current_stage, stage_started_at, next_stage_eta,
        tenant_id, namespace, key, initiator_user_id, approver_user_id,
    ) = row
    version_id = str(version_id)
    if current_stage not in ("5%", "50%"):
        raise ApiError(
            "CONFLICT",
            f"rollout current_stage={current_stage} 非 advance-able stage",
            409,
        )

    now = datetime.now(timezone.utc)
    # 推算 observation 時長（5%→50% 寫入時的 next_stage_eta - stage_started_at）
    if next_stage_eta and stage_started_at:
        observation_seconds = (next_stage_eta - stage_started_at).total_seconds()
    else:
        observation_seconds = 600  # fallback 10 min

    if current_stage == "5%":
        new_stage = "50%"
        new_next_eta = now + timedelta(seconds=observation_seconds)
        await db_module._conn.execute(
            """
            UPDATE saas.config_rollout SET
              current_stage = %s,
              stage_started_at = %s,
              next_stage_eta = %s
            WHERE id = %s::uuid
            """,
            (new_stage, now, new_next_eta, rollout_id),
        )
        await _append_audit(
            tenant_id=str(tenant_id) if tenant_id else None,
            config_version_id=version_id,
            actor_user_id=str(approver_user_id),  # auto-advance 視為 approver 推
            action="stage_advanced",
            diff={
                "from": "5%", "to": "50%",
                "auto_advanced": True,
                "next_stage_eta": new_next_eta.isoformat(),
            },
        )
        return {
            "rollout_id": rollout_id,
            "version_id": version_id,
            "new_stage": new_stage,
            "next_stage_eta": new_next_eta.isoformat(),
        }

    # current_stage == "50%": 推進至 100% + activate
    new_stage = "100%"
    dethroned_id = await _dethrone_active(
        str(tenant_id) if tenant_id else None, namespace, key,
    )
    await db_module._conn.execute(
        """
        UPDATE saas.config_version
        SET state = 'active', activated_at = %s,
            parent_version_id = COALESCE(parent_version_id, %s::uuid)
        WHERE id = %s::uuid
        """,
        (now, dethroned_id, version_id),
    )
    await db_module._conn.execute(
        """
        UPDATE saas.config_rollout SET
          current_stage = %s, stage_started_at = %s,
          next_stage_eta = NULL
        WHERE id = %s::uuid
        """,
        (new_stage, now, rollout_id),
    )
    await _append_audit(
        tenant_id=str(tenant_id) if tenant_id else None,
        config_version_id=version_id,
        actor_user_id=str(approver_user_id),
        action="stage_advanced",
        diff={"from": "50%", "to": "100%", "auto_advanced": True},
    )
    await _append_audit(
        tenant_id=str(tenant_id) if tenant_id else None,
        config_version_id=version_id,
        actor_user_id=str(approver_user_id),
        action="activated",
        diff={"rollout_id": rollout_id, "auto_advanced": True},
    )
    _cache_invalidate(
        str(tenant_id) if tenant_id else None, namespace, key,
    )
    return {
        "rollout_id": rollout_id,
        "version_id": version_id,
        "new_stage": new_stage,
        "next_stage_eta": None,
    }
