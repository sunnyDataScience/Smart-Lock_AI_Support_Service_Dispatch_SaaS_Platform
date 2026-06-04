"""AdminAPIClient — agent → admin api HTTP bridge (ADR-009 D pattern).

統一封裝 5 條 P0 的 HTTP call，含：
- httpx.AsyncClient + 10s timeout
- INTERNAL_API_BEARER auth
- Idempotency-Key header（{line_user_id}:{message_id}:{flow_id}）
- Exponential backoff retry (100ms / 500ms / 2s)
- Fail-soft：失敗不拋；寫 agent_outbox 表（worker phase 2 補實作）
- Logger + alert hook

Env vars（已在 F-010 reschedule postback 既有）:
- INTERNAL_API_BASE_URL（default: http://localhost:8001）
- INTERNAL_API_BEARER（admin JWT bearer）
- INTERNAL_API_TENANT_ID（default tenant uuid）
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("agent.integrations.admin_api")


_DEFAULT_TIMEOUT = 10.0
_RETRY_DELAYS_MS = (100, 500, 2000)  # 3 attempts: 100ms / 500ms / 2s


class AdminAPIClient:
    """Agent → Admin API HTTP client。

    使用方式（agent webhook handler 內）::

        from agent.integrations import AdminAPIClient

        client = AdminAPIClient.from_env()
        conv = await client.create_conversation(
            line_user_id="Uxxx",
            session_id="session-xxx",
            display_name="王小明",
            idempotency_key="Uxxx:msg-12345:F-001-conv",
        )
    """

    def __init__(
        self,
        *,
        base_url: str,
        bearer: str,
        tenant_id: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer = bearer
        self.tenant_id = tenant_id
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "AdminAPIClient":
        return cls(
            base_url=os.environ.get(
                "INTERNAL_API_BASE_URL", "http://localhost:8001"
            ),
            bearer=os.environ.get("INTERNAL_API_BEARER", ""),
            tenant_id=os.environ.get(
                "INTERNAL_API_TENANT_ID", "00000000-0000-0000-0000-000000000001"
            ),
        )

    # ────────────────────────────────────────────────────────────────────
    # Internal: HTTP POST with retry + fail-soft + outbox fallback
    # ────────────────────────────────────────────────────────────────────

    async def _post(
        self,
        *,
        path: str,
        flow_id: str,
        payload: dict,
        idempotency_key: str | None = None,
    ) -> dict | None:
        """POST helper with retry + outbox fallback。

        Returns: response data dict, or None if all retries failed (寫 outbox 後)。
        """
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.bearer}",
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_error: str | None = None
        for attempt, delay_ms in enumerate(_RETRY_DELAYS_MS, start=1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if 200 <= res.status_code < 300:
                        return res.json()
                    # 4xx 不應重試（業務錯誤），記 log 但不寫 outbox
                    if 400 <= res.status_code < 500:
                        logger.warning(
                            "%s %s 4xx (no retry): %s %s",
                            flow_id, url, res.status_code, res.text[:300],
                        )
                        return None
                    # 5xx → retry
                    last_error = f"{res.status_code} {res.text[:200]}"
                    logger.warning(
                        "%s %s attempt %d/%d failed %s",
                        flow_id, url, attempt, len(_RETRY_DELAYS_MS), last_error,
                    )
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "%s %s attempt %d/%d exception %s",
                    flow_id, url, attempt, len(_RETRY_DELAYS_MS), last_error,
                )
            # Sleep before retry（最後一次嘗試後不睡）
            if attempt < len(_RETRY_DELAYS_MS):
                await asyncio.sleep(delay_ms / 1000.0)

        # 全部 retry 失敗 → 寫 outbox + alert
        logger.error(
            "%s %s all retries exhausted; writing to outbox. last_error=%s",
            flow_id, url, last_error,
        )
        await self._write_outbox(
            flow_id=flow_id, endpoint=path, payload=payload,
            headers=headers, last_error=last_error or "unknown",
        )
        return None

    async def _write_outbox(
        self,
        *,
        flow_id: str,
        endpoint: str,
        payload: dict,
        headers: dict,
        last_error: str,
    ) -> None:
        """失敗 fallback：寫 agent_outbox 表（worker phase 2 補重試）。

        此處 import psycopg 於函式內，避免 module-level 對 DB 的硬依賴。
        若 outbox INSERT 也失敗 → 純 logger.error，不再抛（fail-soft 末端）。
        """
        try:
            import json

            import psycopg
        except ImportError:
            logger.error("psycopg not available; outbox write skipped")
            return

        pg_uri = os.environ.get("POSTGRES_URI", "")
        if not pg_uri:
            logger.error("POSTGRES_URI not set; outbox write skipped")
            return

        try:
            async with await psycopg.AsyncConnection.connect(pg_uri) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO agent_outbox "
                        "  (flow_id, endpoint, payload, headers, status, last_error) "
                        "VALUES (%s, %s, %s::jsonb, %s::jsonb, 'pending', %s)",
                        (
                            flow_id, endpoint,
                            json.dumps(payload),
                            json.dumps(
                                {k: v for k, v in headers.items() if k != "Authorization"}
                            ),
                            last_error,
                        ),
                    )
                    await conn.commit()
        except Exception as exc:  # noqa: BLE001 — fail-soft 末端
            logger.error("outbox INSERT failed: %s", exc)

    # ────────────────────────────────────────────────────────────────────
    # F-001: createConversation
    # ────────────────────────────────────────────────────────────────────

    async def create_conversation(
        self,
        *,
        line_user_id: str,
        session_id: str,
        display_name: str | None = None,
        channel: str = "line",
        idempotency_key: str | None = None,
    ) -> dict | None:
        """建立 conversation record（F-001 ServiceTicket）。

        Returns conversation dict or None on failure（已 outbox）。
        """
        payload = {
            "line_user_id": line_user_id,
            "session_id": session_id,
            "channel": channel,
        }
        if display_name:
            payload["display_name"] = display_name

        result = await self._post(
            path=f"/tenants/{self.tenant_id}/conversations",  # P3: tenant-scoped v2（createConversation）
            flow_id="F-001-conv",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return (result or {}).get("data") if result else None

    # ────────────────────────────────────────────────────────────────────
    # F-001 (cont.): createProblemCard
    # ────────────────────────────────────────────────────────────────────

    async def create_problem_card(
        self,
        *,
        conversation_id: str,
        brand: str,
        model: str,
        symptom: str,
        category: str,
        urgency: str = "medium",
        media_urls: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict | None:
        """建立 problem_card record (AI extract 完成後)。"""
        payload = {
            "conversation_id": conversation_id,
            "brand": brand,
            "model": model,
            "symptom": symptom,
            "category": category,
            "urgency": urgency,
        }
        if media_urls:
            payload["media_urls"] = media_urls

        result = await self._post(
            path=f"/tenants/{self.tenant_id}/problem-cards",  # P3: tenant-scoped v2（createProblemCardV2）
            flow_id="F-001-pc",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return (result or {}).get("data") if result else None

    # ────────────────────────────────────────────────────────────────────
    # F-014: createRefundRequest
    # ────────────────────────────────────────────────────────────────────

    async def create_refund_request(
        self,
        *,
        work_order_id: str,
        amount: str,
        reason: str,
        reason_code: str,
        requested_by_role: str = "customer_via_line",
        idempotency_key: str | None = None,
    ) -> dict | None:
        """建立退款申請 (F-014 dual-trigger LINE 自助路徑)。"""
        payload = {
            "work_order_id": work_order_id,
            "amount": amount,
            "reason": reason,
            "reason_code": reason_code,
            "requested_by_role": requested_by_role,
        }
        result = await self._post(
            # CR-0009（2026-06-04 業主拍 HD-02=a）：agent 自動退款走 v2 single-actor
            # path :agent-initiate（ADR-0106 LangGraph 特例；伺服器 role check
            # 必為 agent/system）
            path=f"/tenants/{self.tenant_id}/refunds:agent-initiate",
            flow_id="F-014-refund",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return (result or {}).get("data") if result else None

    # ────────────────────────────────────────────────────────────────────
    # F-015: createWarrantyClaim
    # ────────────────────────────────────────────────────────────────────

    async def create_warranty_claim(
        self,
        *,
        customer_id: str,
        device_brand: str,
        device_model: str,
        claim_type: str,
        requested_by_role: str = "customer_via_line",
        work_order_id: str | None = None,
        purchase_date: str | None = None,
        dispute_reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict | None:
        """建立保固申請 (F-015 dual-trigger LINE 自助路徑)。"""
        payload = {
            "customer_id": customer_id,
            "device_brand": device_brand,
            "device_model": device_model,
            "claim_type": claim_type,
            "requested_by_role": requested_by_role,
        }
        if work_order_id:
            payload["work_order_id"] = work_order_id
        if purchase_date:
            payload["purchase_date"] = purchase_date
        if dispute_reason:
            payload["dispute_reason"] = dispute_reason

        result = await self._post(
            path=f"/tenants/{self.tenant_id}/warranty-claims",  # P3: tenant-scoped v2（createWarrantyClaimV2）
            flow_id="F-015-warranty",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return (result or {}).get("data") if result else None

    # ────────────────────────────────────────────────────────────────────
    # F-017: createSopDraft
    # ────────────────────────────────────────────────────────────────────

    async def create_sop_draft(
        self,
        *,
        source_case_id: str,
        source_type: str,
        draft_content: str,
        model_version: str,
        confidence_score: float | None = None,
        idempotency_key: str | None = None,
    ) -> dict | None:
        """建立 SOP 草稿 (F-017 自進化 case resolved + rating>=4 觸發)。"""
        payload: dict[str, Any] = {
            "source_case_id": source_case_id,
            "source_type": source_type,
            "draft_content": draft_content,
            "model_version": model_version,
        }
        if confidence_score is not None:
            payload["confidence_score"] = confidence_score

        result = await self._post(
            # CR-0006 落地（2026-06-04 業主拍 HD-01=a meta-wrap shape）：
            # 新增 v2 createSopDraftV2 endpoint，agent 改打 tenant-scoped path
            path=f"/tenants/{self.tenant_id}/sops/drafts",
            flow_id="F-017-sop",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return (result or {}).get("data") if result else None
