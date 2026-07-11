"""Idempotency-Key 24h dedup。

流程：
1. 解析 header；無 key 則跳過（GET 或缺 header 視情況拒絕）
2. SELECT 既有 (tenant_id, key) → 命中且 path/method/hash 相符 → 直接回先前 response
3. 不命中 → 設 marker、handler 跑完後寫入 (status, body)
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid as uuid_lib
from typing import Any

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError
import core.db as db_module

logger = logging.getLogger("api.idempotency")


def _hash_request(method: str, path: str, body: bytes) -> str:
    h = hashlib.sha256()
    h.update(method.encode())
    h.update(b"|")
    h.update(path.encode())
    h.update(b"|")
    h.update(body)
    return h.hexdigest()


async def _lookup(tenant_id: str, key: str) -> dict | None:
    if not await _ensure_conn():
        return None
    ttl_hours = int(load_config().idempotency.get("ttl_hours", 24))
    cur = await db_module._conn.execute(
        "SELECT method, path, request_hash, response_status, response_body "
        "FROM idempotency_keys "
        "WHERE tenant_id = %s::uuid AND key = %s "
        "AND created_at > NOW() - (%s * INTERVAL '1 hour')",
        (tenant_id, key, ttl_hours),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "method": row[0],
        "path": row[1],
        "request_hash": row[2],
        "response_status": row[3],
        "response_body": row[4],
    }


async def _store(
    tenant_id: str,
    key: str,
    method: str,
    path: str,
    request_hash: str,
    response_status: int,
    response_body: dict,
) -> None:
    if not await _ensure_conn():
        return
    try:
        await db_module._conn.execute(
            "INSERT INTO idempotency_keys (tenant_id, key, method, path, request_hash, response_status, response_body) "
            "VALUES (%s::uuid, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, key) DO NOTHING",
            (tenant_id, key, method, path, request_hash, response_status, json.dumps(response_body)),
        )
    except Exception as e:
        logger.warning("Idempotency store failed: %s", e)


class IdempotencyContext:
    """掛在 request.state，handler 結束後由 endpoint helper 寫入。"""

    def __init__(self, *, tenant_id: str, key: str, method: str, path: str, request_hash: str):
        self.tenant_id = tenant_id
        self.key = key
        self.method = method
        self.path = path
        self.request_hash = request_hash

    async def save(self, status_code: int, body: Any) -> None:
        if isinstance(body, (dict, list)):
            payload = body
        else:
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": str(body)}
        await _store(self.tenant_id, self.key, self.method, self.path, self.request_hash, status_code, payload)


# CR-0165 F12：公開無登入端點（技師/廠商註冊）client 無從得知 tenant，
# 缺 X-Tenant-ID 時 fallback 到公共命名空間（zero-UUID）而非靜默 no-op。
PUBLIC_TENANT_NAMESPACE = "00000000-0000-0000-0000-000000000000"


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid_lib.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


async def _guard_impl(
    request: Request,
    idempotency_key: str | None,
    x_tenant_id: str | None,
    *,
    default_tenant: str | None,
) -> IdempotencyContext | None:
    cfg = load_config().idempotency
    if not idempotency_key:
        # 強制策略：寫操作必填
        if request.method.upper() in cfg.get("applies_to", []):
            raise ApiError(
                error_code="MISSING_IDEMPOTENCY_KEY",
                message=f"Idempotency-Key header is required for {request.method} requests",
                status_code=400,
            )
        return None

    if x_tenant_id and not _is_valid_uuid(x_tenant_id):
        # CR-0165 F12：原 %s::uuid cast 遇非 UUID 直接 psycopg 錯誤 → 500；改 400
        raise ApiError(
            error_code="VALIDATION_ERROR",
            message="X-Tenant-ID 須為合法 UUID",
            status_code=400,
        )

    if not x_tenant_id:
        if default_tenant is None:
            # 沒 tenant 就無法 dedup（一般已登入端點前端恆帶 header）
            return None
        # CR-0165 F12：公開註冊端點 opt-in fallback（原本靜默 fail-open 不去重）
        x_tenant_id = default_tenant

    body = await request.body()
    request_hash = _hash_request(request.method, request.url.path, body)

    cached = await _lookup(x_tenant_id, idempotency_key)
    if cached:
        if cached["request_hash"] != request_hash:
            raise ApiError(
                error_code="IDEMPOTENCY_KEY_MISMATCH",
                message="Same Idempotency-Key used with different request payload",
                status_code=409,
            )
        # Replay
        raise IdempotencyReplay(cached["response_status"], cached["response_body"])

    return IdempotencyContext(
        tenant_id=x_tenant_id,
        key=idempotency_key,
        method=request.method,
        path=request.url.path,
        request_hash=request_hash,
    )


async def idempotency_guard(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> IdempotencyContext | None:
    """寫操作建議套用此 dependency。

    - 缺 key → 回 None（呼叫方決定是否強制要求）
    - 命中 → 拋 ApiError(replay) 攜帶已存 response
    - 未命中 → 回 IdempotencyContext，handler 完成後手動 save()
    """
    return await _guard_impl(
        request, idempotency_key, x_tenant_id, default_tenant=None
    )


def make_idempotency_guard(*, default_tenant: str):
    """CR-0165 F12：帶預設命名空間的 guard 工廠——公開無登入端點專用。

    缺 X-Tenant-ID 時以 default_tenant 作為 (tenant_id, key) 命名空間，
    使 curl/外部整合方只帶 Idempotency-Key 也能正常去重回放。
    """

    async def _dep(
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> IdempotencyContext | None:
        return await _guard_impl(
            request, idempotency_key, x_tenant_id, default_tenant=default_tenant
        )

    return _dep


class IdempotencyReplay(Exception):
    """命中 idempotency cache → 由 main.py 的 exception handler 回放。"""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body


async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
