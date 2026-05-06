"""WebSocket pub-sub hub（in-memory；單機 MVP）。

設計：
  - channel → set[WebSocket] 簡單映射，asyncio Lock 保護
  - publish(channel, payload) → 對該 channel 所有連線 send_json，失敗自動斷線回收
  - 多進程 / 多 worker 部署時需改用 Redis pub-sub（後續迭代）

頻道命名（對齊 docs/02-design/specs/asyncapi.yaml）：
  /realtime/notifications/{user_id}
  /realtime/work-orders/{id}
  /realtime/dispatch-queue
  /realtime/sla-alerts
  /realtime/refunds / /realtime/disputes / /realtime/inventory/low-stock / /realtime/rbac
  /realtime/pool/{tech_id}
  /realtime/diagnostics/{conv_id}（SSE，不在此 hub）

訊息格式：JSON `{ "type": "<event-name>", "payload": {...} }`
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from core.auth import decode_token, is_jti_revoked

logger = logging.getLogger("api.ws_hub")


@dataclass
class WSAuth:
    """WS 連線通過驗證後的身份資訊。"""

    user_id: str
    role: str
    tenant_id: str
    jti: str


class WSAuthError(Exception):
    """WS 認證失敗（送 close code + reason 給 client）。"""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


async def verify_ws_token(
    *, access_token: str | None, tenant_id_query: str | None
) -> WSAuth:
    """驗 access_token + tenant_id 一致性。失敗丟 WSAuthError（含 close code）。"""
    if not access_token:
        raise WSAuthError(1008, "missing access_token")
    try:
        payload = decode_token(access_token)
    except Exception as e:  # noqa: BLE001
        raise WSAuthError(1008, "invalid_token") from e
    if payload.get("type") != "access":
        raise WSAuthError(1008, "wrong_token_type")
    jti = payload.get("jti", "")
    if jti and await is_jti_revoked(jti):
        raise WSAuthError(1008, "token_revoked")
    user_tenant = payload.get("tenant_id", "")
    if tenant_id_query and user_tenant and tenant_id_query != user_tenant:
        raise WSAuthError(1008, "tenant_mismatch")
    return WSAuth(
        user_id=payload["sub"],
        role=payload.get("role", ""),
        tenant_id=user_tenant,
        jti=jti,
    )


def authorize_channel(*, channel: str, auth: WSAuth, path_user_id: str | None = None, path_tech_id: str | None = None, allowed_roles: set[str] | None = None) -> None:
    """檢查連線使用者對該 channel 是否有授權。失敗丟 WSAuthError(1008)。

    - path_user_id：若 channel 含 {user_id}，須等於 token sub
    - path_tech_id：若 channel 含 {tech_id}，須等於 token sub（技師訂閱自己的 pool）
                    或 admin role 可訂閱任何技師（管理員監控用）
    - allowed_roles：若給定，token role 必須在集合內
    """
    if path_user_id and path_user_id != auth.user_id:
        raise WSAuthError(1008, "user_id_mismatch")
    if path_tech_id and path_tech_id != auth.user_id and auth.role not in {"admin", "operations_manager"}:
        raise WSAuthError(1008, "tech_id_mismatch")
    if allowed_roles is not None and auth.role not in allowed_roles:
        raise WSAuthError(1008, f"role_not_allowed:{auth.role}")


class WSHub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(ws)
        logger.info("ws subscribe channel=%s subscribers=%d", channel, len(self._channels.get(channel, set())))

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs:
                subs.discard(ws)
                if not subs:
                    self._channels.pop(channel, None)
        logger.info("ws unsubscribe channel=%s remaining=%d", channel, len(self._channels.get(channel, set())))

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """對 channel 所有連線送出 JSON message。回傳成功 send 的 connection 數。"""
        async with self._lock:
            subs = list(self._channels.get(channel, set()))
        if not subs:
            return 0
        sent = 0
        dead: list[WebSocket] = []
        for ws in subs:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception as e:  # noqa: BLE001 — 任何錯誤都標 dead
                logger.warning("ws send failed channel=%s err=%s", channel, e)
                dead.append(ws)
        if dead:
            async with self._lock:
                bucket = self._channels.get(channel)
                if bucket:
                    for ws in dead:
                        bucket.discard(ws)
                    if not bucket:
                        self._channels.pop(channel, None)
        return sent

    def channel_count(self) -> int:
        return len(self._channels)


# 單例 hub（進程內共用）
hub = WSHub()
