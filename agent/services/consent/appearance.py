"""Appearance change consent service.

When a technician's work may alter the door's appearance (e.g. cutting a
Korean-standard side panel causes paint bubbling), the customer must give
informed consent before the technician proceeds.

This service manages the consent lifecycle and integrates with the existing
``appearance_change_consents`` table defined in SQL/Schema.sql.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

_VALID_CONSENT_METHODS = frozenset({
    "digital_signature",
    "line_confirmation",
    "verbal_recorded",
})


class ConsentError(Exception):
    """Base error for consent operations."""


class ConsentNotFoundError(ConsentError):
    """Raised when the requested consent record does not exist."""


class AppearanceConsentService:
    """Manages appearance change consent requests and approvals.

    Operates against the ``appearance_change_consents`` table. Once a
    consent record is created it is immutable except for recording the
    customer's decision (consented / not consented).
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.environ.get(db_uri_env, "")
        if not self._db_uri:
            raise EnvironmentError(
                f"Environment variable '{db_uri_env}' is not set or empty."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(
            self._db_uri, row_factory=dict_row
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_consent_request(
        self,
        work_order_id: str,
        technician_id: str,
        customer_id: str,
        change_description: str,
        affected_area: str | None = None,
        original_photo_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new appearance change consent request.

        The consent starts with ``customer_consented = NULL`` (pending).
        The technician must wait for customer confirmation before proceeding
        with the work that would alter the door's appearance.
        """
        consent_id = str(uuid.uuid4())

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO appearance_change_consents
                        (id, work_order_id, technician_id, customer_id,
                         change_description, affected_area, original_photo_urls)
                    VALUES
                        (%(id)s, %(wo)s, %(tech)s, %(cust)s,
                         %(desc)s, %(area)s, %(photos)s::jsonb)
                    RETURNING *
                    """,
                    {
                        "id": consent_id,
                        "wo": work_order_id,
                        "tech": technician_id,
                        "cust": customer_id,
                        "desc": change_description,
                        "area": affected_area,
                        "photos": (
                            psycopg.types.json.Json(original_photo_urls)
                            if original_photo_urls
                            else None
                        ),
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Created appearance consent request %s for work_order %s",
            consent_id,
            work_order_id,
        )
        return dict(row)  # type: ignore[arg-type]

    async def record_consent(
        self,
        consent_id: str,
        consented: bool,
        method: str,
    ) -> dict[str, Any]:
        """Record the customer's consent decision.

        Args:
            consent_id: UUID of the consent request.
            consented: True if the customer agrees, False if declined.
            method: One of ``digital_signature``, ``line_confirmation``,
                    ``verbal_recorded``.

        Raises:
            ConsentNotFoundError: if consent_id does not exist.
            ValueError: if method is not a recognised consent method.
        """
        if method not in _VALID_CONSENT_METHODS:
            raise ValueError(
                f"Invalid consent method '{method}'. "
                f"Must be one of: {', '.join(sorted(_VALID_CONSENT_METHODS))}."
            )

        now = datetime.now(timezone.utc)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE appearance_change_consents
                       SET customer_consented = %(consented)s,
                           consented_at = %(now)s,
                           consent_method = %(method)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": consent_id,
                        "consented": consented,
                        "now": now,
                        "method": method,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        if row is None:
            raise ConsentNotFoundError(f"Consent request '{consent_id}' not found.")

        logger.info(
            "Consent %s recorded: consented=%s method=%s",
            consent_id,
            consented,
            method,
        )
        return dict(row)

    async def get_consent(self, consent_id: str) -> dict[str, Any] | None:
        """Fetch a single consent request by ID."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM appearance_change_consents WHERE id = %(id)s",
                    {"id": consent_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None
        return dict(row)

    async def get_consents_for_work_order(
        self, work_order_id: str
    ) -> list[dict[str, Any]]:
        """List all consent requests associated with a work order."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM appearance_change_consents
                     WHERE work_order_id = %(wo)s
                     ORDER BY created_at ASC
                    """,
                    {"wo": work_order_id},
                )
                rows = await cur.fetchall()

        return [dict(r) for r in rows]

    async def check_consent_required(self, work_order_id: str) -> bool:
        """Check whether there are pending (unanswered) consent requests.

        Returns True if at least one consent request exists for this work
        order with ``customer_consented IS NULL``.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM appearance_change_consents
                         WHERE work_order_id = %(wo)s
                           AND customer_consented IS NULL
                    ) AS pending
                    """,
                    {"wo": work_order_id},
                )
                row = await cur.fetchone()

        return bool(row and row["pending"])

    @staticmethod
    def generate_line_notification(consent_request: dict[str, Any]) -> dict[str, Any]:
        """Generate a LINE Flex Message payload for customer notification.

        The message describes the proposed appearance change, shows the
        before-photos, and provides confirm/decline action buttons.

        This is a pure function -- it does not perform I/O.
        """
        consent_id = consent_request["id"]
        description = consent_request.get("change_description", "")
        affected_area = consent_request.get("affected_area", "")
        photo_urls: list[str] = consent_request.get("original_photo_urls") or []

        # Build image components for before-photos.
        image_components = [
            {
                "type": "image",
                "url": url,
                "size": "full",
                "aspectRatio": "4:3",
                "aspectMode": "cover",
            }
            for url in photo_urls[:3]  # limit to 3 images
        ]

        flex_message: dict[str, Any] = {
            "type": "flex",
            "altText": "Door appearance change consent required",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "Door Appearance Change Notice",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#1a1a1a",
                        }
                    ],
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": description,
                            "wrap": True,
                            "size": "sm",
                        },
                        {
                            "type": "text",
                            "text": f"Affected area: {affected_area}" if affected_area else "",
                            "wrap": True,
                            "size": "xs",
                            "color": "#888888",
                        },
                        *image_components,
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "action": {
                                "type": "postback",
                                "label": "Agree",
                                "data": f"consent_approve:{consent_id}",
                            },
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "action": {
                                "type": "postback",
                                "label": "Decline",
                                "data": f"consent_decline:{consent_id}",
                            },
                        },
                    ],
                },
            },
        }

        return flex_message
