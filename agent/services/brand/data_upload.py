"""Brand OEM data upload and processing service.

Handles file uploads from brand OEM partners (manuals, fault codes,
firmware changelogs, warranty policies) and integrates them into the
platform knowledge base.

Processing pipeline: upload -> validate -> process -> integrate into KB.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB

_ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "manual_pdf": {".pdf"},
    "fault_code_table": {".json", ".csv", ".xlsx"},
    "firmware_changelog": {".json", ".csv", ".pdf"},
    "warranty_policy": {".pdf", ".json"},
}


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class UploadType(str, Enum):
    """Categories of data a brand OEM can upload."""

    MANUAL_PDF = "manual_pdf"
    FAULT_CODE_TABLE = "fault_code_table"
    FIRMWARE_CHANGELOG = "firmware_changelog"
    WARRANTY_POLICY = "warranty_policy"


class UploadStatus(str, Enum):
    """Lifecycle states of a brand data upload."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BrandUpload:
    """Represents a single brand data upload record."""

    id: str
    brand_id: str
    upload_type: UploadType
    filename: str
    file_size_bytes: int
    status: UploadStatus
    error_message: str | None
    uploaded_by: str
    processed_at: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "brand_id": self.brand_id,
            "upload_type": self.upload_type.value,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status.value,
            "error_message": self.error_message,
            "uploaded_by": self.uploaded_by,
            "processed_at": self.processed_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UploadError(Exception):
    """Base error for upload operations."""


class ValidationError(UploadError):
    """Raised when file validation fails."""


class UploadNotFoundError(UploadError):
    """Raised when the upload record does not exist."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BrandDataUploadService:
    """Manages brand OEM data uploads and processing pipeline.

    Files are stored on disk under *upload_dir* and metadata is persisted
    in the ``brand_uploads`` database table.  After upload, each file is
    validated and processed according to its type, then integrated into
    the relevant knowledge base tables.
    """

    def __init__(
        self,
        db_uri_env: str = "POSTGRES_URI",
        upload_dir: str = "./data/uploads/brands",
    ) -> None:
        self._db_uri = os.environ.get(db_uri_env, "")
        if not self._db_uri:
            raise EnvironmentError(
                f"Environment variable '{db_uri_env}' is not set or empty."
            )
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

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

    @staticmethod
    def _row_to_upload(row: dict[str, Any]) -> BrandUpload:
        return BrandUpload(
            id=row["id"],
            brand_id=row["brand_id"],
            upload_type=UploadType(row["upload_type"]),
            filename=row["filename"],
            file_size_bytes=row["file_size_bytes"],
            status=UploadStatus(row["status"]),
            error_message=row.get("error_message"),
            uploaded_by=row["uploaded_by"],
            processed_at=str(row["processed_at"]) if row.get("processed_at") else None,
            created_at=str(row["created_at"]),
        )

    def _brand_dir(self, brand_id: str) -> Path:
        d = self._upload_dir / brand_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _file_path(self, brand_id: str, upload_id: str, filename: str) -> Path:
        return self._brand_dir(brand_id) / f"{upload_id}_{filename}"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_file(
        self,
        filename: str,
        file_data: bytes,
        upload_type: UploadType,
    ) -> tuple[bool, str]:
        """Validate file size and extension against upload type rules.

        Returns (is_valid, error_message). When valid, error_message is
        an empty string.
        """
        if len(file_data) > MAX_FILE_SIZE_BYTES:
            return False, (
                f"File exceeds maximum size of "
                f"{MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        if len(file_data) == 0:
            return False, "File is empty."

        ext = Path(filename).suffix.lower()
        allowed = _ALLOWED_EXTENSIONS.get(upload_type.value, set())
        if ext not in allowed:
            return False, (
                f"Extension '{ext}' is not allowed for upload type "
                f"'{upload_type.value}'. Allowed: {sorted(allowed)}"
            )

        return True, ""

    # ------------------------------------------------------------------
    # Type-specific processors
    # ------------------------------------------------------------------

    async def _process_manual_pdf(
        self, file_path: Path, brand_id: str
    ) -> dict[str, Any]:
        """Trigger the existing PDF-to-RAG pipeline for product manuals.

        TODO: integrate with the RAG ingestion pipeline to parse, chunk,
        embed, and insert into the manuals table + vector store.
        """
        logger.info(
            "Processing manual PDF %s for brand %s", file_path, brand_id
        )
        return {
            "action": "manual_pdf_ingestion",
            "file": str(file_path),
            "brand_id": brand_id,
            "status": "queued",
        }

    async def _process_fault_codes(
        self, file_path: Path, brand_id: str
    ) -> dict[str, Any]:
        """Parse brand-specific fault codes and merge into fault_trees.

        Supports JSON and CSV formats.  Each row maps a fault code to
        its description, severity, and recommended actions.

        TODO: implement merge logic against knowledge/fault_trees/.
        """
        ext = file_path.suffix.lower()
        logger.info(
            "Processing fault codes (%s) %s for brand %s",
            ext,
            file_path,
            brand_id,
        )
        return {
            "action": "fault_code_merge",
            "file": str(file_path),
            "brand_id": brand_id,
            "format": ext,
            "status": "queued",
        }

    async def _process_firmware_changelog(
        self, file_path: Path, brand_id: str
    ) -> dict[str, Any]:
        """Index firmware changelog entries for case_entries references.

        TODO: parse changelog and create searchable entries.
        """
        logger.info(
            "Processing firmware changelog %s for brand %s",
            file_path,
            brand_id,
        )
        return {
            "action": "firmware_changelog_index",
            "file": str(file_path),
            "brand_id": brand_id,
            "status": "queued",
        }

    async def _process_warranty_policy(
        self, file_path: Path, brand_id: str
    ) -> dict[str, Any]:
        """Ingest warranty policy for automated warranty verification.

        TODO: parse terms and map to warranty_policies table.
        """
        logger.info(
            "Processing warranty policy %s for brand %s",
            file_path,
            brand_id,
        )
        return {
            "action": "warranty_policy_ingestion",
            "file": str(file_path),
            "brand_id": brand_id,
            "status": "queued",
        }

    _PROCESSORS = {
        UploadType.MANUAL_PDF: "_process_manual_pdf",
        UploadType.FAULT_CODE_TABLE: "_process_fault_codes",
        UploadType.FIRMWARE_CHANGELOG: "_process_firmware_changelog",
        UploadType.WARRANTY_POLICY: "_process_warranty_policy",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_upload(
        self,
        brand_id: str,
        upload_type: UploadType | str,
        filename: str,
        file_data: bytes,
        uploaded_by: str,
    ) -> BrandUpload:
        """Persist a new file upload and save it to disk.

        Validates the file before storing. On success the upload record
        is created with ``pending`` status, ready for processing.

        Raises:
            ValidationError: if the file fails validation checks.
        """
        if isinstance(upload_type, str):
            upload_type = UploadType(upload_type)

        is_valid, err = self._validate_file(filename, file_data, upload_type)
        if not is_valid:
            raise ValidationError(err)

        upload_id = str(uuid.uuid4())
        dest = self._file_path(brand_id, upload_id, filename)
        dest.write_bytes(file_data)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO brand_uploads
                        (id, brand_id, upload_type, filename,
                         file_size_bytes, status, uploaded_by, file_path)
                    VALUES
                        (%(id)s, %(brand_id)s, %(upload_type)s,
                         %(filename)s, %(file_size)s, 'pending',
                         %(uploaded_by)s, %(file_path)s)
                    RETURNING *
                    """,
                    {
                        "id": upload_id,
                        "brand_id": brand_id,
                        "upload_type": upload_type.value,
                        "filename": filename,
                        "file_size": len(file_data),
                        "uploaded_by": uploaded_by,
                        "file_path": str(dest),
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Created upload %s (%s, %d bytes) for brand %s",
            upload_id,
            upload_type.value,
            len(file_data),
            brand_id,
        )
        return self._row_to_upload(row)  # type: ignore[arg-type]

    async def process_upload(self, upload_id: str) -> BrandUpload:
        """Run the type-specific processing pipeline for an upload.

        Transitions status from ``pending`` to ``processing``, invokes
        the appropriate processor, then sets ``completed`` or ``failed``.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM brand_uploads WHERE id = %(id)s FOR UPDATE",
                    {"id": upload_id},
                )
                row = await cur.fetchone()
                if row is None:
                    raise UploadNotFoundError(
                        f"Upload '{upload_id}' not found."
                    )

                if UploadStatus(row["status"]) != UploadStatus.PENDING:
                    raise UploadError(
                        f"Upload '{upload_id}' is not in pending state "
                        f"(current: {row['status']})."
                    )

                # Mark as processing.
                await cur.execute(
                    """
                    UPDATE brand_uploads SET status = 'processing'
                     WHERE id = %(id)s
                    """,
                    {"id": upload_id},
                )
            await conn.commit()

        upload_type = UploadType(row["upload_type"])
        file_path = Path(row["file_path"])
        brand_id: str = row["brand_id"]

        processor_name = self._PROCESSORS.get(upload_type)
        error_message: str | None = None
        final_status = UploadStatus.COMPLETED

        try:
            processor = getattr(self, processor_name)
            await processor(file_path, brand_id)
        except Exception as exc:
            logger.exception(
                "Processing failed for upload %s: %s", upload_id, exc
            )
            error_message = str(exc)
            final_status = UploadStatus.FAILED

        now = self._now_iso()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE brand_uploads
                       SET status = %(status)s,
                           error_message = %(error)s,
                           processed_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": upload_id,
                        "status": final_status.value,
                        "error": error_message,
                        "now": now,
                    },
                )
                updated = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Upload %s processing finished: %s", upload_id, final_status.value
        )
        return self._row_to_upload(updated)  # type: ignore[arg-type]

    async def get_upload(self, upload_id: str) -> BrandUpload | None:
        """Retrieve a single upload record by ID."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM brand_uploads WHERE id = %(id)s",
                    {"id": upload_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None
        return self._row_to_upload(row)

    async def list_uploads(
        self,
        brand_id: str,
        upload_type: UploadType | str | None = None,
    ) -> list[BrandUpload]:
        """List uploads for a brand, optionally filtered by type."""
        query = "SELECT * FROM brand_uploads WHERE brand_id = %(brand_id)s"
        params: dict[str, Any] = {"brand_id": brand_id}

        if upload_type is not None:
            if isinstance(upload_type, str):
                upload_type = UploadType(upload_type)
            query += " AND upload_type = %(upload_type)s"
            params["upload_type"] = upload_type.value

        query += " ORDER BY created_at DESC"

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        return [self._row_to_upload(r) for r in rows]

    async def delete_upload(self, upload_id: str) -> bool:
        """Delete an upload record and its file from disk.

        Returns True if the record existed and was deleted, False otherwise.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT file_path FROM brand_uploads WHERE id = %(id)s",
                    {"id": upload_id},
                )
                row = await cur.fetchone()
                if row is None:
                    return False

                file_path = Path(row["file_path"])
                if file_path.exists():
                    file_path.unlink()

                await cur.execute(
                    "DELETE FROM brand_uploads WHERE id = %(id)s",
                    {"id": upload_id},
                )
            await conn.commit()

        logger.info("Deleted upload %s", upload_id)
        return True
