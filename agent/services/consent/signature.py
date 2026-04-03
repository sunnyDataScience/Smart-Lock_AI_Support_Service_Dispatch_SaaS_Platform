"""Electronic signature service for service documents.

Supports three signature methods:
  - LINE confirmation: customer taps a confirm button in LINE Flex Message
  - Digital signature: canvas-based handwritten signature capture
  - Verbal recorded: phone call recording reference (legacy)

Each signature record includes an integrity hash (SHA-256) for
non-repudiation and compliance with Taiwan's Electronic Signatures Act.
"""

from __future__ import annotations

import enum
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class SignatureMethod(str, enum.Enum):
    """Supported signature methods."""

    LINE_CONFIRMATION = "line_confirmation"
    DIGITAL_SIGNATURE = "digital_signature"
    VERBAL_RECORDED = "verbal_recorded"


class DocumentType(str, enum.Enum):
    """Document types that can be signed."""

    WORK_ORDER_COMPLETION = "work_order_completion"
    APPEARANCE_CHANGE = "appearance_change"
    REFUND_ACCEPTANCE = "refund_acceptance"
    SCOPE_CHANGE = "scope_change"


@dataclass
class SignatureRecord:
    """Snapshot of a single electronic signature."""

    id: str
    signer_id: str
    signer_role: str
    document_type: str
    document_id: str
    signature_method: str
    signature_data: dict[str, Any] | None
    ip_address: str | None
    signed_at: datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SignatureError(Exception):
    """Base error for signature operations."""


class SignatureNotFoundError(SignatureError):
    """Raised when the requested signature record does not exist."""


class ESignatureService:
    """Manages electronic signatures for platform documents.

    All database operations use async psycopg connections obtained from
    the connection URI stored in the environment variable *db_uri_env*.
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

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> SignatureRecord:
        return SignatureRecord(
            id=str(row["id"]),
            signer_id=str(row["signer_id"]),
            signer_role=row["signer_role"],
            document_type=row["document_type"],
            document_id=str(row["document_id"]),
            signature_method=row["signature_method"],
            signature_data=row.get("signature_data"),
            ip_address=str(row["ip_address"]) if row.get("ip_address") else None,
            signed_at=row["signed_at"],
        )

    @staticmethod
    def _compute_integrity_hash(
        signer_id: str,
        signer_role: str,
        document_type: str,
        document_id: str,
        signature_method: str,
        signed_at: datetime,
    ) -> str:
        """Compute SHA-256 hash over key fields for non-repudiation.

        The hash covers the identity of the signer, the document reference,
        the method used, and the timestamp -- providing a tamper-evident
        seal without requiring external PKI.
        """
        payload = (
            f"{signer_id}|{signer_role}|{document_type}|"
            f"{document_id}|{signature_method}|{signed_at.isoformat()}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_signature(
        self,
        signer_id: str,
        signer_role: str,
        document_type: DocumentType | str,
        document_id: str,
        method: SignatureMethod | str,
        signature_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SignatureRecord:
        """Create and persist a new electronic signature.

        Args:
            signer_id: UUID of the person signing.
            signer_role: ``customer``, ``technician``, or ``admin``.
            document_type: Type of document being signed.
            document_id: UUID of the related document (work order, consent, etc.).
            method: Signature method used.
            signature_data: Method-specific payload (see spec for JSONB schema).
            ip_address: Signer's IP address for audit trail.
            user_agent: Signer's browser/client string.

        Returns:
            The persisted SignatureRecord.
        """
        if isinstance(document_type, str):
            document_type = DocumentType(document_type)
        if isinstance(method, str):
            method = SignatureMethod(method)

        sig_id = str(uuid.uuid4())
        signed_at = datetime.now(timezone.utc)

        integrity_hash = self._compute_integrity_hash(
            signer_id=signer_id,
            signer_role=signer_role,
            document_type=document_type.value,
            document_id=document_id,
            signature_method=method.value,
            signed_at=signed_at,
        )

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO digital_signatures
                        (id, signer_id, signer_role, document_type, document_id,
                         signature_method, signature_data, ip_address, user_agent,
                         integrity_hash, signed_at)
                    VALUES
                        (%(id)s, %(signer)s, %(role)s, %(doc_type)s, %(doc_id)s,
                         %(method)s, %(data)s::jsonb, %(ip)s::inet, %(ua)s,
                         %(hash)s, %(signed_at)s)
                    RETURNING *
                    """,
                    {
                        "id": sig_id,
                        "signer": signer_id,
                        "role": signer_role,
                        "doc_type": document_type.value,
                        "doc_id": document_id,
                        "method": method.value,
                        "data": (
                            psycopg.types.json.Json(signature_data)
                            if signature_data
                            else None
                        ),
                        "ip": ip_address,
                        "ua": user_agent,
                        "hash": integrity_hash,
                        "signed_at": signed_at,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Created signature %s: signer=%s doc=%s:%s method=%s",
            sig_id,
            signer_id,
            document_type.value,
            document_id,
            method.value,
        )
        return self._row_to_record(row)  # type: ignore[arg-type]

    async def verify_signature(self, signature_id: str) -> dict[str, Any]:
        """Verify a signature's integrity by recomputing its hash.

        Returns:
            Dict with keys: ``valid``, ``signer_id``, ``signer_role``,
            ``signed_at``, ``signature_method``.

        Raises:
            SignatureNotFoundError: if the signature does not exist.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM digital_signatures WHERE id = %(id)s",
                    {"id": signature_id},
                )
                row = await cur.fetchone()

        if row is None:
            raise SignatureNotFoundError(
                f"Signature '{signature_id}' not found."
            )

        expected_hash = self._compute_integrity_hash(
            signer_id=str(row["signer_id"]),
            signer_role=row["signer_role"],
            document_type=row["document_type"],
            document_id=str(row["document_id"]),
            signature_method=row["signature_method"],
            signed_at=row["signed_at"],
        )

        stored_hash = row.get("integrity_hash", "")
        valid = expected_hash == stored_hash

        if not valid:
            logger.warning(
                "Integrity check FAILED for signature %s: "
                "expected=%s stored=%s",
                signature_id,
                expected_hash,
                stored_hash,
            )

        return {
            "valid": valid,
            "signer_id": str(row["signer_id"]),
            "signer_role": row["signer_role"],
            "signed_at": row["signed_at"],
            "signature_method": row["signature_method"],
        }

    async def get_signatures_for_document(
        self,
        document_type: DocumentType | str,
        document_id: str,
    ) -> list[SignatureRecord]:
        """Retrieve all signatures for a specific document."""
        if isinstance(document_type, str):
            document_type = DocumentType(document_type)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM digital_signatures
                     WHERE document_type = %(type)s
                       AND document_id = %(id)s
                     ORDER BY signed_at ASC
                    """,
                    {"type": document_type.value, "id": document_id},
                )
                rows = await cur.fetchall()

        return [self._row_to_record(r) for r in rows]

    async def is_document_signed(
        self,
        document_type: DocumentType | str,
        document_id: str,
    ) -> bool:
        """Check whether at least one valid signature exists for a document."""
        if isinstance(document_type, str):
            document_type = DocumentType(document_type)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM digital_signatures
                         WHERE document_type = %(type)s
                           AND document_id = %(id)s
                    ) AS signed
                    """,
                    {"type": document_type.value, "id": document_id},
                )
                row = await cur.fetchone()

        return bool(row and row["signed"])

    @staticmethod
    def generate_line_confirm_payload(
        document_type: DocumentType | str,
        document_id: str,
        description: str,
    ) -> dict[str, Any]:
        """Generate a LINE Flex Message payload for signature collection.

        The message presents the document description and a single
        "Confirm" button whose postback carries the document reference
        for server-side verification.

        This is a pure function -- it does not perform I/O.
        """
        if isinstance(document_type, str):
            document_type = DocumentType(document_type)

        postback_data = f"sign:{document_type.value}:{document_id}"

        # Map document types to human-readable titles.
        title_map = {
            DocumentType.WORK_ORDER_COMPLETION: "Service Completion Confirmation",
            DocumentType.APPEARANCE_CHANGE: "Appearance Change Consent",
            DocumentType.REFUND_ACCEPTANCE: "Refund Acceptance Confirmation",
            DocumentType.SCOPE_CHANGE: "Scope Change Approval",
        }
        title = title_map.get(document_type, "Document Confirmation")

        flex_message: dict[str, Any] = {
            "type": "flex",
            "altText": title,
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": title,
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
                            "type": "separator",
                        },
                        {
                            "type": "text",
                            "text": (
                                "By tapping 'Confirm' below, you agree to the "
                                "above terms. This action constitutes your "
                                "electronic signature."
                            ),
                            "wrap": True,
                            "size": "xs",
                            "color": "#888888",
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#1DB446",
                            "action": {
                                "type": "postback",
                                "label": "Confirm",
                                "data": postback_data,
                            },
                        },
                    ],
                },
            },
        }

        return flex_message
