"""Evidence package assembly for dispute resolution.

Collects supporting evidence from related tables (problem_cards,
conversations, work_orders.photos, invoices, warranty_claims,
scope_changes) and bundles them into a structured package that
can be exported for review or arbitration.

Related schema: disputes (id, work_order_id, invoice_id, filed_by,
dispute_type, status, description, evidence JSONB, resolution,
resolution_amount, resolved_by, sla_deadline).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    """Categories of evidence that can be attached to a dispute."""

    PROBLEM_CARD = "problem_card"
    CONVERSATION_SUMMARY = "conversation_summary"
    BEFORE_PHOTO = "before_photo"
    AFTER_PHOTO = "after_photo"
    QUOTE_DOCUMENT = "quote_document"
    CUSTOMER_CONFIRMATION = "customer_confirmation"
    TECHNICIAN_REPORT = "technician_report"
    INVOICE = "invoice"
    WARRANTY_CLAIM = "warranty_claim"
    SCOPE_CHANGE = "scope_change"


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence attached to a dispute."""

    evidence_type: EvidenceType
    title: str
    content_or_url: str
    collected_at: str  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "title": self.title,
            "content_or_url": self.content_or_url,
            "collected_at": self.collected_at,
        }


@dataclass
class EvidencePackage:
    """Complete evidence bundle for a single dispute."""

    dispute_id: str
    work_order_id: str
    items: list[EvidenceItem] = field(default_factory=list)
    generated_at: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispute_id": self.dispute_id,
            "work_order_id": self.work_order_id,
            "items": [item.to_dict() for item in self.items],
            "generated_at": self.generated_at,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvidenceError(Exception):
    """Base error for evidence operations."""


class DisputeNotFoundError(EvidenceError):
    """Raised when the dispute record does not exist."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EvidencePackageService:
    """Assembles, stores, and exports evidence packages for disputes.

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
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Evidence collectors — each returns items from a related table
    # ------------------------------------------------------------------

    async def _collect_problem_card(
        self, work_order_id: str
    ) -> EvidenceItem | None:
        """Fetch the problem card linked to a work order."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, lock_type, symptoms, diagnostic_result,
                           created_at
                      FROM problem_cards
                     WHERE work_order_id = %(wo)s
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    {"wo": work_order_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None

        content = json.dumps(dict(row), default=str, ensure_ascii=False)
        return EvidenceItem(
            evidence_type=EvidenceType.PROBLEM_CARD,
            title=f"Problem Card #{row['id']}",
            content_or_url=content,
            collected_at=self._now_iso(),
        )

    async def _collect_conversation(
        self, work_order_id: str
    ) -> EvidenceItem | None:
        """Fetch conversation summary for the work order."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, summary, channel, created_at
                      FROM conversations
                     WHERE work_order_id = %(wo)s
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    {"wo": work_order_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None

        content = json.dumps(dict(row), default=str, ensure_ascii=False)
        return EvidenceItem(
            evidence_type=EvidenceType.CONVERSATION_SUMMARY,
            title=f"Conversation Summary ({row['channel']})",
            content_or_url=content,
            collected_at=self._now_iso(),
        )

    async def _collect_photos(
        self, work_order_id: str
    ) -> list[EvidenceItem]:
        """Fetch before/after photos linked to the work order."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, photo_type, url, uploaded_at
                      FROM work_order_photos
                     WHERE work_order_id = %(wo)s
                     ORDER BY uploaded_at ASC
                    """,
                    {"wo": work_order_id},
                )
                rows = await cur.fetchall()

        items: list[EvidenceItem] = []
        for row in rows:
            photo_type = row.get("photo_type", "unknown")
            if photo_type == "before":
                etype = EvidenceType.BEFORE_PHOTO
            elif photo_type == "after":
                etype = EvidenceType.AFTER_PHOTO
            else:
                etype = EvidenceType.BEFORE_PHOTO

            items.append(
                EvidenceItem(
                    evidence_type=etype,
                    title=f"{photo_type.capitalize()} Photo #{row['id']}",
                    content_or_url=row["url"],
                    collected_at=self._now_iso(),
                )
            )
        return items

    async def _collect_financial_docs(
        self, work_order_id: str, invoice_id: str | None
    ) -> list[EvidenceItem]:
        """Fetch invoice, quote, and scope-change documents."""
        items: list[EvidenceItem] = []

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                # Invoice
                if invoice_id:
                    await cur.execute(
                        "SELECT * FROM invoices WHERE id = %(id)s",
                        {"id": invoice_id},
                    )
                    inv = await cur.fetchone()
                    if inv:
                        items.append(
                            EvidenceItem(
                                evidence_type=EvidenceType.INVOICE,
                                title=f"Invoice #{inv['id']}",
                                content_or_url=json.dumps(
                                    dict(inv), default=str, ensure_ascii=False
                                ),
                                collected_at=self._now_iso(),
                            )
                        )

                # Quote document (from work_orders table)
                await cur.execute(
                    """
                    SELECT id, quote_amount, quote_document_url
                      FROM work_orders
                     WHERE id = %(wo)s AND quote_document_url IS NOT NULL
                    """,
                    {"wo": work_order_id},
                )
                quote = await cur.fetchone()
                if quote and quote.get("quote_document_url"):
                    items.append(
                        EvidenceItem(
                            evidence_type=EvidenceType.QUOTE_DOCUMENT,
                            title=f"Quote for WO #{work_order_id}",
                            content_or_url=quote["quote_document_url"],
                            collected_at=self._now_iso(),
                        )
                    )

                # Warranty claims
                await cur.execute(
                    """
                    SELECT id, claim_type, status, description, created_at
                      FROM warranty_claims
                     WHERE work_order_id = %(wo)s
                     ORDER BY created_at ASC
                    """,
                    {"wo": work_order_id},
                )
                for wc in await cur.fetchall():
                    items.append(
                        EvidenceItem(
                            evidence_type=EvidenceType.WARRANTY_CLAIM,
                            title=f"Warranty Claim #{wc['id']}",
                            content_or_url=json.dumps(
                                dict(wc), default=str, ensure_ascii=False
                            ),
                            collected_at=self._now_iso(),
                        )
                    )

                # Scope changes
                await cur.execute(
                    """
                    SELECT id, change_type, description,
                           old_amount, new_amount, created_at
                      FROM scope_changes
                     WHERE work_order_id = %(wo)s
                     ORDER BY created_at ASC
                    """,
                    {"wo": work_order_id},
                )
                for sc in await cur.fetchall():
                    items.append(
                        EvidenceItem(
                            evidence_type=EvidenceType.SCOPE_CHANGE,
                            title=f"Scope Change #{sc['id']}",
                            content_or_url=json.dumps(
                                dict(sc), default=str, ensure_ascii=False
                            ),
                            collected_at=self._now_iso(),
                        )
                    )

        return items

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assemble_package(self, dispute_id: str) -> EvidencePackage:
        """Auto-collect evidence from all related tables and persist.

        Reads the dispute row to obtain work_order_id and invoice_id,
        then queries problem_cards, conversations, photos, invoices,
        warranty_claims, and scope_changes to build a complete package.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM disputes WHERE id = %(id)s",
                    {"id": dispute_id},
                )
                dispute = await cur.fetchone()

        if dispute is None:
            raise DisputeNotFoundError(f"Dispute '{dispute_id}' not found.")

        work_order_id: str = dispute["work_order_id"]
        invoice_id: str | None = dispute.get("invoice_id")

        # Collect from all sources concurrently-safe (sequential for clarity).
        items: list[EvidenceItem] = []

        problem_card = await self._collect_problem_card(work_order_id)
        if problem_card:
            items.append(problem_card)

        conversation = await self._collect_conversation(work_order_id)
        if conversation:
            items.append(conversation)

        items.extend(await self._collect_photos(work_order_id))
        items.extend(
            await self._collect_financial_docs(work_order_id, invoice_id)
        )

        package = EvidencePackage(
            dispute_id=dispute_id,
            work_order_id=work_order_id,
            items=items,
            generated_at=self._now_iso(),
        )

        package.summary = await self.generate_summary(package)

        # Persist the assembled evidence back to the dispute row.
        evidence_json = json.dumps(
            package.to_dict(), default=str, ensure_ascii=False
        )
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE disputes
                       SET evidence = %(evidence)s::jsonb
                     WHERE id = %(id)s
                    """,
                    {"id": dispute_id, "evidence": evidence_json},
                )
            await conn.commit()

        logger.info(
            "Assembled evidence package for dispute %s (%d items)",
            dispute_id,
            len(items),
        )
        return package

    async def add_evidence(
        self,
        dispute_id: str,
        evidence_type: EvidenceType | str,
        title: str,
        content_or_url: str,
    ) -> dict[str, Any]:
        """Manually add a single evidence item to an existing dispute.

        Appends to the JSONB ``evidence.items`` array in the disputes table.
        Returns the newly added item as a dict.
        """
        if isinstance(evidence_type, str):
            evidence_type = EvidenceType(evidence_type)

        item = EvidenceItem(
            evidence_type=evidence_type,
            title=title,
            content_or_url=content_or_url,
            collected_at=self._now_iso(),
        )

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT evidence FROM disputes WHERE id = %(id)s FOR UPDATE",
                    {"id": dispute_id},
                )
                row = await cur.fetchone()
                if row is None:
                    raise DisputeNotFoundError(
                        f"Dispute '{dispute_id}' not found."
                    )

                existing: dict[str, Any] = row.get("evidence") or {}
                items_list: list[dict[str, Any]] = existing.get("items", [])
                items_list.append(item.to_dict())
                existing["items"] = items_list

                await cur.execute(
                    """
                    UPDATE disputes
                       SET evidence = %(evidence)s::jsonb
                     WHERE id = %(id)s
                    """,
                    {
                        "id": dispute_id,
                        "evidence": json.dumps(
                            existing, default=str, ensure_ascii=False
                        ),
                    },
                )
            await conn.commit()

        logger.info(
            "Added %s evidence to dispute %s",
            evidence_type.value,
            dispute_id,
        )
        return item.to_dict()

    async def get_package(self, dispute_id: str) -> EvidencePackage | None:
        """Retrieve the stored evidence package for a dispute.

        Returns None if no evidence has been assembled yet.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT evidence, work_order_id FROM disputes WHERE id = %(id)s",
                    {"id": dispute_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None

        evidence: dict[str, Any] | None = row.get("evidence")
        if not evidence:
            return None

        items = [
            EvidenceItem(
                evidence_type=EvidenceType(i["evidence_type"]),
                title=i["title"],
                content_or_url=i["content_or_url"],
                collected_at=i["collected_at"],
            )
            for i in evidence.get("items", [])
        ]

        return EvidencePackage(
            dispute_id=dispute_id,
            work_order_id=evidence.get("work_order_id", row["work_order_id"]),
            items=items,
            generated_at=evidence.get("generated_at", ""),
            summary=evidence.get("summary", ""),
        )

    async def generate_summary(self, package: EvidencePackage) -> str:
        """Produce a structured text summary of all evidence items.

        The summary lists each evidence category with counts and key
        details, suitable for inclusion in a dispute resolution report.
        """
        if not package.items:
            return "No evidence collected."

        lines: list[str] = [
            f"Evidence Package for Dispute {package.dispute_id}",
            f"Work Order: {package.work_order_id}",
            f"Generated: {package.generated_at}",
            f"Total Items: {len(package.items)}",
            "",
            "--- Items ---",
        ]

        by_type: dict[str, list[EvidenceItem]] = {}
        for item in package.items:
            by_type.setdefault(item.evidence_type.value, []).append(item)

        for etype, eitems in by_type.items():
            lines.append(f"\n[{etype.upper()}] ({len(eitems)} item(s))")
            for ei in eitems:
                # Truncate long content for summary readability.
                preview = ei.content_or_url[:200]
                if len(ei.content_or_url) > 200:
                    preview += "..."
                lines.append(f"  - {ei.title}: {preview}")

        return "\n".join(lines)

    async def export_package(
        self, dispute_id: str, format: str = "json"
    ) -> str:
        """Export the evidence package to a file and return its path.

        Supported formats: ``json``.

        Raises:
            DisputeNotFoundError: if the dispute does not exist.
            EvidenceError: if no evidence has been assembled.
            ValueError: if the format is unsupported.
        """
        if format != "json":
            raise ValueError(f"Unsupported export format: '{format}'")

        package = await self.get_package(dispute_id)
        if package is None:
            raise EvidenceError(
                f"No evidence package found for dispute '{dispute_id}'. "
                "Run assemble_package first."
            )

        export_dir = Path("./data/exports/disputes")
        export_dir.mkdir(parents=True, exist_ok=True)

        filename = f"dispute_{dispute_id}_{self._now_iso()[:10]}.json"
        file_path = export_dir / filename

        file_path.write_text(
            json.dumps(package.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        logger.info("Exported evidence package to %s", file_path)
        return str(file_path)
