"""Idempotency-Key 24h dedup（UAT R3-6 起改 reserve-first 先佔）。

流程（reserve-first，已釘契約）：
1. 解析 header；無 key 則跳過（GET 或缺 header 視情況拒絕）
2. handler 執行前先 INSERT 佔位列（status='in_progress'）
3. INSERT 撞 (tenant_id, key) 既有列時：
   - status='completed' 且 hash 相符 → 回放已存 response
   - status='completed' 但 hash 不符 → 409 IDEMPOTENCY_KEY_MISMATCH
   - status='in_progress'（且未逾時）→ 409 IDEMPOTENCY_IN_PROGRESS（客戶端稍後重試）
   - 列已逾期（TTL 過）或 in_progress 逾時（handler 掛掉殘留）→ 原子接管重佔
4. handler 成功 → save() 把佔位列補成 completed + response
5. handler 失敗（未 save）→ dependency finally 釋放佔位列（錯誤回應不快取，
   客戶端可立即用同 key 重試 —— 對齊改造前「失敗不入快取」語意）

舊版 check-then-act（先 SELECT 再事後 INSERT）在同 key 併發 2 發時雙雙 miss →
handler 執行兩次（UAT R3-6：同一張問題卡兩張工單＋發票錯亂）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid as uuid_lib
from typing import Any, AsyncIterator

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError
import core.db as db_module

logger = logging.getLogger("api.idempotency")

#: in_progress 佔位逾時秒數（handler 掛掉殘留的接管窗；非 409 重試建議值）
_DEFAULT_RESERVE_TTL_SECONDS = 300


def _hash_request(method: str, path: str, body: bytes) -> str:
    h = hashlib.sha256()
    h.update(method.encode())
    h.update(b"|")
    h.update(path.encode())
    h.update(b"|")
    h.update(body)
    return h.hexdigest()


async def _try_insert_reservation(
    tenant_id: str, key: str, method: str, path: str, request_hash: str
) -> bool:
    """INSERT 佔位列；成功=True，撞既有列=False。"""
    cur = await db_module._conn.execute(
        "INSERT INTO idempotency_keys "
        "  (tenant_id, key, method, path, request_hash, status) "
        "VALUES (%s::uuid, %s, %s, %s, %s, 'in_progress') "
        "ON CONFLICT (tenant_id, key) DO NOTHING "
        "RETURNING key",
        (tenant_id, key, method, path, request_hash),
    )
    return (await cur.fetchone()) is not None


async def _try_takeover(
    tenant_id: str, key: str, method: str, path: str, request_hash: str,
    ttl_hours: int, reserve_ttl_seconds: int,
) -> bool:
    """原子接管逾期列（TTL 過的 completed / 逾時的 in_progress 殘留）。

    UPDATE 帶時間條件 —— 併發下只有一個請求能接管成功。
    """
    cur = await db_module._conn.execute(
        "UPDATE idempotency_keys "
        "SET method = %s, path = %s, request_hash = %s, "
        "    status = 'in_progress', response_status = NULL, response_body = NULL, "
        "    created_at = NOW() "
        "WHERE tenant_id = %s::uuid AND key = %s "
        "  AND ( created_at <= NOW() - (%s * INTERVAL '1 hour') "
        "        OR (status = 'in_progress' "
        "            AND created_at <= NOW() - (%s * INTERVAL '1 second')) ) "
        "RETURNING key",
        (method, path, request_hash, tenant_id, key, ttl_hours, reserve_ttl_seconds),
    )
    return (await cur.fetchone()) is not None


async def _fetch_existing(tenant_id: str, key: str) -> dict | None:
    cur = await db_module._conn.execute(
        "SELECT method, path, request_hash, response_status, response_body, status "
        "FROM idempotency_keys "
        "WHERE tenant_id = %s::uuid AND key = %s",
        (tenant_id, key),
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
        "status": row[5],
    }


async def _complete(
    tenant_id: str,
    key: str,
    response_status: int,
    response_body: dict,
) -> None:
    """handler 成功後把佔位列補成 completed（無佔位列時容錯直接 INSERT）。"""
    try:
        cur = await db_module._conn.execute(
            "UPDATE idempotency_keys "
            "SET status = 'completed', response_status = %s, response_body = %s "
            "WHERE tenant_id = %s::uuid AND key = %s "
            "RETURNING key",
            (response_status, json.dumps(response_body), tenant_id, key),
        )
        if await cur.fetchone():
            return
        # 佔位列消失（極端：接管競態）→ 保底 INSERT，維持回放能力
        await db_module._conn.execute(
            "INSERT INTO idempotency_keys "
            "  (tenant_id, key, method, path, request_hash, response_status, response_body, status) "
            "VALUES (%s::uuid, %s, '', '', '', %s, %s, 'completed') "
            "ON CONFLICT (tenant_id, key) DO NOTHING",
            (tenant_id, key, response_status, json.dumps(response_body)),
        )
    except Exception as e:
        logger.warning("Idempotency store failed: %s", e)


async def _release_reservation(tenant_id: str, key: str) -> None:
    """handler 失敗（未 save）→ 刪掉自己的 in_progress 佔位列。

    只刪 in_progress：completed 列（已 save 或他人接管完成）不動。
    錯誤回應不快取 —— 客戶端可立即用同 key 重試（維持改造前語意）。
    """
    try:
        await db_module._conn.execute(
            "DELETE FROM idempotency_keys "
            "WHERE tenant_id = %s::uuid AND key = %s AND status = 'in_progress'",
            (tenant_id, key),
        )
    except Exception as e:
        logger.warning("Idempotency release failed: %s", e)


class IdempotencyContext:
    """掛在 request.state，handler 結束後由 endpoint helper 寫入。"""

    def __init__(self, *, tenant_id: str, key: str, method: str, path: str, request_hash: str):
        self.tenant_id = tenant_id
        self.key = key
        self.method = method
        self.path = path
        self.request_hash = request_hash
        self.saved = False

    async def save(self, status_code: int, body: Any) -> None:
        if isinstance(body, (dict, list)):
            payload = body
        else:
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": str(body)}
        await _complete(self.tenant_id, self.key, status_code, payload)
        self.saved = True


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

    if not await _ensure_conn():
        # DB 不可用 → 無法 dedup（與舊版 _lookup fail-open 行為一致，不擋業務）
        return None

    ttl_hours = int(cfg.get("ttl_hours", 24))
    reserve_ttl = int(cfg.get("reserve_ttl_seconds", _DEFAULT_RESERVE_TTL_SECONDS))
    ctx = IdempotencyContext(
        tenant_id=x_tenant_id,
        key=idempotency_key,
        method=request.method,
        path=request.url.path,
        request_hash=request_hash,
    )

    # reserve-first：先佔 → 成功者才執行 handler
    if await _try_insert_reservation(
        x_tenant_id, idempotency_key, request.method, request.url.path, request_hash
    ):
        return ctx

    # 撞既有列：接管逾期列 → 否則依 status 回放 / 409
    if await _try_takeover(
        x_tenant_id, idempotency_key, request.method, request.url.path, request_hash,
        ttl_hours, reserve_ttl,
    ):
        return ctx

    existing = await _fetch_existing(x_tenant_id, idempotency_key)
    if existing is None:
        # 競態邊角：列在 takeover 檢查與 SELECT 之間被釋放 → 再佔一次
        if await _try_insert_reservation(
            x_tenant_id, idempotency_key, request.method, request.url.path, request_hash
        ):
            return ctx
        raise ApiError(
            error_code="IDEMPOTENCY_IN_PROGRESS",
            message="相同 Idempotency-Key 的請求正在處理中，請稍後重試",
            status_code=409,
        )

    if existing["request_hash"] != request_hash:
        raise ApiError(
            error_code="IDEMPOTENCY_KEY_MISMATCH",
            message="Same Idempotency-Key used with different request payload",
            status_code=409,
        )

    if existing["status"] == "completed":
        # Replay
        raise IdempotencyReplay(existing["response_status"], existing["response_body"])

    # in_progress（未逾時）→ 客戶端稍後重試
    raise ApiError(
        error_code="IDEMPOTENCY_IN_PROGRESS",
        message="相同 Idempotency-Key 的請求正在處理中，請稍後重試",
        status_code=409,
    )


async def idempotency_guard(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> AsyncIterator[IdempotencyContext | None]:
    """寫操作建議套用此 dependency（yield 形式）。

    - 缺 key → 回 None（呼叫方決定是否強制要求）
    - 既有 completed 命中 → 拋 IdempotencyReplay 回放已存 response
    - 同 key in_progress → 409 IDEMPOTENCY_IN_PROGRESS
    - 成功先佔 → 回 IdempotencyContext，handler 完成後手動 save()；
      未 save（handler 拋錯）由本 dependency finally 釋放佔位列
    """
    ctx = await _guard_impl(
        request, idempotency_key, x_tenant_id, default_tenant=None
    )
    if ctx is None:
        yield None
        return
    try:
        yield ctx
    finally:
        if not ctx.saved:
            await _release_reservation(ctx.tenant_id, ctx.key)


def make_idempotency_guard(*, default_tenant: str):
    """CR-0165 F12：帶預設命名空間的 guard 工廠——公開無登入端點專用。

    缺 X-Tenant-ID 時以 default_tenant 作為 (tenant_id, key) 命名空間，
    使 curl/外部整合方只帶 Idempotency-Key 也能正常去重回放。
    """

    async def _dep(
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> AsyncIterator[IdempotencyContext | None]:
        ctx = await _guard_impl(
            request, idempotency_key, x_tenant_id, default_tenant=default_tenant
        )
        if ctx is None:
            yield None
            return
        try:
            yield ctx
        finally:
            if not ctx.saved:
                await _release_reservation(ctx.tenant_id, ctx.key)

    return _dep


class IdempotencyReplay(Exception):
    """命中 idempotency cache → 由 main.py 的 exception handler 回放。"""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body


async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
