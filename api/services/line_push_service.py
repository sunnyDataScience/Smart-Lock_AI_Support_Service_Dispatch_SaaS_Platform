"""LINE Messaging API Push wrapper for the REST API service.

設計原則
========
- **Fail-soft**：LINE_CHANNEL_ACCESS_TOKEN 缺失或推送失敗時不 raise，回 False + log。
  通知失敗不應該阻斷主業務流程（reschedule / delay 工單必須先寫 DB）。
- **Retry on transient errors**：429 (rate limit) / 5xx → backoff 1s/2s/4s，最多 3 次。
- **Audit on every attempt**：成功/失敗均寫 audit_events，便於後續排查與 SLA 統計。
- **Tenant-aware**：解析 work_order → user.line_user_id 時做 tenant 隔離。
- **No side-effects on import**：Configuration 在第一次呼叫時 lazy-init，
  讓單元測試可以 monkeypatch `_get_configuration` 而不需要實際 token。

對齊
====
- F-010 改約 / 延遲 → notify_delay / request_reschedule / approve_reschedule
- F-018 殘留 LINE Push API integration（conversation_service.py:304 TODO）
- Q8=A V1.0：only LINE 用戶；非 LINE 客戶 → notification_sent=false（不視為錯誤）
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from services import audit_log_service

logger = logging.getLogger("api.line_push_service")


# Lazy-loaded LINE SDK Configuration; tests can monkeypatch `_get_configuration`.
_configuration: Any = None


def _get_configuration() -> Any:
    """Lazy-init Configuration once per process.

    Token absent → return None so callers fail-soft and log a "no token"
    audit instead of crashing.
    """
    global _configuration
    if _configuration is not None:
        return _configuration
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        return None
    try:
        from linebot.v3.messaging import Configuration  # noqa: WPS433 — defer SDK import

        _configuration = Configuration(access_token=token)
        return _configuration
    except Exception as exc:  # noqa: BLE001 — SDK not installed → fail-soft
        logger.warning("LINE SDK unavailable: %s", exc)
        return None


def reset_configuration_cache() -> None:
    """Test helper: reset the cached Configuration to force re-init."""
    global _configuration
    _configuration = None


# ---------------------------------------------------------------------------
# Core push (with retry + audit)
# ---------------------------------------------------------------------------


# Transient HTTP statuses that warrant a retry.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = (1, 2, 4)  # three retries with exponential backoff


async def _audit(
    *,
    line_user_id: str,
    success: bool,
    error: str | None,
    work_order_id: str | None,
    actor_user_id: str | None,
    tenant_id: str | None,
    text_len: int,
    attempts: int,
) -> None:
    """Write a single audit_event row for a push attempt (success or failure)."""
    payload: dict[str, Any] = {
        "line_user_id": line_user_id,
        "text_len": text_len,
        "attempts": attempts,
        "success": success,
    }
    if error:
        payload["error"] = error[:500]
    await audit_log_service.log_event(
        event_type="line_push",
        actor_id=actor_user_id,
        actor_role=None,
        action="line_push.success" if success else "line_push.failure",
        target_type="work_order" if work_order_id else None,
        target_id=work_order_id,
        payload=payload,
    )


async def push_text(
    *,
    line_user_id: str,
    text: str,
    work_order_id: str | None = None,
    actor_user_id: str | None = None,
    tenant_id: str | None = None,
) -> bool:
    """Push a text message to one LINE user.

    Returns True if the LINE API accepted the request, False otherwise.
    Never raises — callers can rely on the boolean.
    """
    if not line_user_id:
        logger.info("line_push skipped: empty line_user_id")
        return False

    text = (text or "").strip()
    if not text:
        logger.info("line_push skipped: empty text")
        return False

    cfg = _get_configuration()
    if cfg is None:
        await _audit(
            line_user_id=line_user_id,
            success=False,
            error="LINE_CHANNEL_ACCESS_TOKEN missing",
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            text_len=len(text),
            attempts=0,
        )
        logger.warning("line_push skipped: LINE_CHANNEL_ACCESS_TOKEN missing")
        return False

    # LINE single message limit ≈ 5000 chars; truncate defensively.
    text = text[:5000]

    last_error: str | None = None
    attempts = 0
    success = False

    try:
        from linebot.v3.messaging import (  # noqa: WPS433
            ApiException,
            AsyncApiClient,
            AsyncMessagingApi,
            PushMessageRequest,
            TextMessage,
        )

        for backoff in _BACKOFF_SECONDS:
            attempts += 1
            try:
                async with AsyncApiClient(cfg) as api_client:
                    api = AsyncMessagingApi(api_client)
                    await api.push_message(
                        PushMessageRequest(
                            to=line_user_id,
                            messages=[TextMessage(text=text)],
                        )
                    )
                success = True
                last_error = None
                break
            except ApiException as exc:  # noqa: PERF203
                status = getattr(exc, "status", None)
                last_error = f"ApiException status={status} body={getattr(exc, 'body', '')!s:.200s}"
                if status not in _RETRYABLE_STATUSES:
                    break
                # Sleep before next retry (skip on last iteration handled by loop end)
                await asyncio.sleep(backoff)
            except Exception as exc:  # noqa: BLE001 — network / parse errors → retry
                last_error = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(backoff)
    except Exception as exc:  # noqa: BLE001 — SDK import failure → fail-soft
        last_error = f"SDK import failed: {exc}"

    if not success:
        logger.warning(
            "line_push failed user=%s attempts=%d err=%s",
            line_user_id,
            attempts,
            last_error,
        )
    else:
        logger.info(
            "line_push ok user=%s attempts=%d wo=%s",
            line_user_id,
            attempts,
            work_order_id,
        )

    try:
        await _audit(
            line_user_id=line_user_id,
            success=success,
            error=last_error,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            text_len=len(text),
            attempts=attempts,
        )
    except Exception:  # noqa: BLE001 — audit must never break caller
        logger.warning("line_push audit write failed", exc_info=True)

    return success


# ---------------------------------------------------------------------------
# Helper: resolve work_order → customer LINE user_id (tenant-scoped)
# ---------------------------------------------------------------------------


async def resolve_customer_line_user_id(
    *, tenant_id: str, work_order_id: str
) -> str | None:
    """Find customer's line_user_id via work_order → problem_card → conversation → user.

    Returns None when:
      - work order not found / not in tenant
      - customer is not a LINE user (line_user_id IS NULL — Q8=A V1.0 only LINE)
    """
    if not await _ensure_conn():
        logger.warning("resolve_customer_line_user_id: DB unavailable")
        return None

    sql = (
        "SELECT u.line_user_id "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (work_order_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        return None
    return row[0] or None


async def push_to_work_order_customer(
    *,
    tenant_id: str,
    work_order_id: str,
    text: str,
    actor_user_id: str | None = None,
) -> tuple[bool, str]:
    """Convenience: resolve customer then push.

    Returns (notification_sent, channel) where:
      - channel='line' when push attempted (success or transient retry exhausted)
      - channel='none' when customer is not a LINE user (V1.0 拒收非 LINE)
    """
    line_user_id = await resolve_customer_line_user_id(
        tenant_id=tenant_id, work_order_id=work_order_id
    )
    if not line_user_id:
        return (False, "none")
    sent = await push_text(
        line_user_id=line_user_id,
        text=text,
        work_order_id=work_order_id,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
    )
    return (sent, "line")
