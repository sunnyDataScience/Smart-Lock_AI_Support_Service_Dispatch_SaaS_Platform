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

    if not x_tenant_id:
        # 沒 tenant 就無法 dedup（auth 端點不會走到這）
        return None

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


class IdempotencyReplay(Exception):
    """命中 idempotency cache → 由 main.py 的 exception handler 回放。"""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body


async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
