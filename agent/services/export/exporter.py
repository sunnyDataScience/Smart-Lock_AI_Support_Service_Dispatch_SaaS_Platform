"""
Data export engine for Smart Lock AI Support SaaS Platform.

GAP #14 -- Data Export / Portability (Contract 9-3).

Supports async export of conversations, work orders, financial records,
and personal data in CSV, JSON, or PDF format with optional PII masking.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExportScope(str, Enum):
    """Determines which data domain to export."""

    CONVERSATIONS = "conversations"
    WORK_ORDERS = "work_orders"
    FINANCIAL = "financial"
    PERSONAL_DATA = "personal_data"


class ExportFormat(str, Enum):
    """Supported output file formats."""

    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class ExportStatus(str, Enum):
    """Lifecycle states for an export job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExportRequest:
    """Tracks a single export job from creation to expiry."""

    id: str
    user_id: str
    scope: ExportScope
    format: ExportFormat
    filters: dict[str, Any] = field(default_factory=dict)
    mask_pii: bool = False
    status: ExportStatus = ExportStatus.PENDING
    file_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=72),
    )


# ---------------------------------------------------------------------------
# PII field patterns used by the masking logic
# ---------------------------------------------------------------------------

_PII_FIELDS = frozenset({
    "phone", "mobile", "telephone",
    "email", "email_address",
    "address", "home_address", "shipping_address",
    "id_number", "national_id", "identity_number",
})

# File TTL -- generated exports auto-expire after this duration.
_EXPORT_TTL = timedelta(hours=72)


# ---------------------------------------------------------------------------
# DataExporter
# ---------------------------------------------------------------------------

class DataExporter:
    """Orchestrates data export jobs.

    Parameters
    ----------
    db_uri_env:
        Name of the environment variable holding the PostgreSQL connection URI.
    export_dir:
        Local directory where generated export files are stored.
    """

    def __init__(
        self,
        db_uri_env: str = "POSTGRES_URI",
        export_dir: str = "./data/exports",
    ) -> None:
        self._db_uri = os.getenv(db_uri_env, "")
        self._export_dir = Path(export_dir)
        self._export_dir.mkdir(parents=True, exist_ok=True)

        # In-memory registry; production should be backed by a database table.
        self._requests: dict[str, ExportRequest] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_export(
        self,
        user_id: str,
        scope: ExportScope,
        fmt: ExportFormat,
        filters: dict[str, Any] | None = None,
        mask_pii: bool = False,
    ) -> ExportRequest:
        """Create a new pending export request.

        Returns the ``ExportRequest`` so the caller can return its ``id``
        to the client immediately (HTTP 202).
        """
        export_id = f"exp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        req = ExportRequest(
            id=export_id,
            user_id=user_id,
            scope=scope,
            format=fmt,
            filters=filters or {},
            mask_pii=mask_pii,
            status=ExportStatus.PENDING,
            created_at=now,
            expires_at=now + _EXPORT_TTL,
        )
        self._requests[export_id] = req
        logger.info("Export request created: %s scope=%s format=%s", export_id, scope.value, fmt.value)
        return req

    async def process_export(self, export_id: str) -> str:
        """Execute the export job and return the resulting file path.

        This method is intended to be called by a background worker.

        Raises
        ------
        ValueError
            If the export request does not exist.
        RuntimeError
            If the export fails during processing.
        """
        req = self._requests.get(export_id)
        if req is None:
            raise ValueError(f"Export request not found: {export_id}")

        req.status = ExportStatus.PROCESSING
        logger.info("Processing export: %s", export_id)

        try:
            scope_handlers: dict[ExportScope, Any] = {
                ExportScope.CONVERSATIONS: self._export_conversations,
                ExportScope.WORK_ORDERS: self._export_work_orders,
                ExportScope.FINANCIAL: self._export_financial,
                ExportScope.PERSONAL_DATA: self._export_personal_data,
            }

            handler = scope_handlers[req.scope]

            if req.scope == ExportScope.FINANCIAL:
                file_path = await handler(req.filters, req.format, req.mask_pii)
            elif req.scope == ExportScope.PERSONAL_DATA:
                file_path = await handler(req.user_id, req.format)
            else:
                file_path = await handler(req.user_id, req.filters, req.format, req.mask_pii)

            req.file_path = file_path
            req.status = ExportStatus.COMPLETED
            logger.info("Export completed: %s -> %s", export_id, file_path)
            return file_path

        except Exception:
            req.status = ExportStatus.FAILED
            logger.exception("Export failed: %s", export_id)
            raise RuntimeError(f"Export processing failed for {export_id}") from None

    async def get_export_status(self, export_id: str) -> ExportRequest | None:
        """Return the current state of an export request, or ``None``."""
        req = self._requests.get(export_id)
        if req is None:
            return None

        # Mark expired on read.
        if req.status == ExportStatus.COMPLETED and datetime.now(timezone.utc) >= req.expires_at:
            req.status = ExportStatus.EXPIRED
        return req

    async def cleanup_expired(self) -> int:
        """Delete files and records for expired exports. Returns count removed."""
        now = datetime.now(timezone.utc)
        removed = 0
        expired_ids: list[str] = []

        for eid, req in self._requests.items():
            if now >= req.expires_at:
                if req.file_path:
                    path = Path(req.file_path)
                    if path.exists():
                        path.unlink()
                        logger.info("Deleted expired export file: %s", path)
                expired_ids.append(eid)
                removed += 1

        for eid in expired_ids:
            del self._requests[eid]

        logger.info("Cleanup completed: %d expired exports removed", removed)
        return removed

    # ------------------------------------------------------------------
    # Scope-specific export handlers (private)
    # ------------------------------------------------------------------

    async def _export_conversations(
        self,
        user_id: str,
        filters: dict[str, Any],
        fmt: ExportFormat,
        mask_pii: bool,
    ) -> str:
        """Export user conversation history.

        Production implementation queries the conversations and messages
        tables filtered by *user_id* and optional date/status filters.
        """
        # Placeholder: fetch from database.
        data: list[dict[str, Any]] = []
        # TODO: query conversations table WHERE user_id = :user_id

        if mask_pii:
            data = [self._mask_record(row) for row in data]

        filepath = self._build_filepath("conversations", user_id, fmt)
        await self._write(data, filepath, fmt)
        return str(filepath)

    async def _export_work_orders(
        self,
        user_id: str,
        filters: dict[str, Any],
        fmt: ExportFormat,
        mask_pii: bool,
    ) -> str:
        """Export work order records including status history."""
        data: list[dict[str, Any]] = []
        # TODO: query work_orders + status_history tables

        if mask_pii:
            data = [self._mask_record(row) for row in data]

        filepath = self._build_filepath("work_orders", user_id, fmt)
        await self._write(data, filepath, fmt)
        return str(filepath)

    async def _export_financial(
        self,
        filters: dict[str, Any],
        fmt: ExportFormat,
        mask_pii: bool,
    ) -> str:
        """Export financial records (invoices, payments, refunds).

        This scope is admin-only and requires the ``finance`` role permission.
        Authorization is enforced at the API layer before this method is called.
        """
        data: list[dict[str, Any]] = []
        # TODO: query invoices, payments, refunds tables

        if mask_pii:
            data = [self._mask_record(row) for row in data]

        filepath = self._build_filepath("financial", "all", fmt)
        await self._write(data, filepath, fmt)
        return str(filepath)

    async def _export_personal_data(
        self,
        user_id: str,
        fmt: ExportFormat,
    ) -> str:
        """Export user profile and PII (GDPR-style data portability).

        PII masking is NOT applied here -- the purpose of this scope is to
        give the user their complete personal data.
        """
        data: list[dict[str, Any]] = []
        # TODO: query users table + preferences

        filepath = self._build_filepath("personal_data", user_id, fmt)
        await self._write(data, filepath, fmt)
        return str(filepath)

    # ------------------------------------------------------------------
    # PII masking
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_pii_value(field_name: str, value: str) -> str:
        """Mask a PII value, preserving leading/trailing characters for recognition.

        Returns the original value unchanged if *field_name* is not a known PII field.
        """
        normalized = field_name.lower().strip()
        if normalized not in _PII_FIELDS:
            return value

        if not value or len(value) < 3:
            return "***"

        if normalized in ("email", "email_address") and "@" in value:
            local, domain = value.rsplit("@", 1)
            masked_local = local[0] + "***" if local else "***"
            return f"{masked_local}@{domain}"

        if normalized in ("phone", "mobile", "telephone"):
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 6:
                masked = digits[:4] + "***" + digits[-3:]
                return masked
            return "***"

        # Generic: keep first and last characters.
        if len(value) <= 4:
            return value[0] + "***" + value[-1]
        return value[0] + "*" * (len(value) - 2) + value[-1]

    def _mask_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Apply PII masking to all recognised PII fields in a flat dict."""
        masked: dict[str, Any] = {}
        for key, val in record.items():
            if isinstance(val, str):
                masked[key] = self._mask_pii_value(key, val)
            else:
                masked[key] = val
        return masked

    # ------------------------------------------------------------------
    # File writers
    # ------------------------------------------------------------------

    async def _write(
        self,
        data: list[dict[str, Any]],
        filepath: Path,
        fmt: ExportFormat,
    ) -> None:
        """Dispatch to the correct writer based on format."""
        if fmt == ExportFormat.CSV:
            self._write_csv(data, filepath)
        elif fmt == ExportFormat.JSON:
            self._write_json(data, filepath)
        elif fmt == ExportFormat.PDF:
            # PDF generation is delegated to a dedicated library.
            # Placeholder writes JSON as a fallback; replace with reportlab/weasyprint.
            logger.warning("PDF export not yet implemented; falling back to JSON for %s", filepath)
            self._write_json(data, filepath.with_suffix(".json"))
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

    @staticmethod
    def _write_csv(data: list[dict[str, Any]], filepath: Path) -> None:
        """Write a list of flat dicts to a CSV file."""
        if not data:
            filepath.write_text("", encoding="utf-8")
            return

        fieldnames = list(data[0].keys())
        with filepath.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    @staticmethod
    def _write_json(data: list[dict[str, Any]], filepath: Path) -> None:
        """Write structured data to a JSON file."""
        with filepath.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_filepath(self, scope: str, user_id: str, fmt: ExportFormat) -> Path:
        """Construct a unique file path under the export directory."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        suffix = fmt.value if fmt != ExportFormat.PDF else "pdf"
        filename = f"{scope}_{user_id}_{ts}_{uuid.uuid4().hex[:6]}.{suffix}"
        return self._export_dir / filename
