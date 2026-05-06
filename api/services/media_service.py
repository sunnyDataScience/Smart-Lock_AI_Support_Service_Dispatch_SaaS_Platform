"""媒體檔案 service（T8 photos / 完工照片 / dispute evidence）。

對應：
  POST   /api/v1/media                    upload
  GET    /api/v1/media/{id}               serve
  GET    /api/v1/work-orders/{id}/media   list by work order

儲存策略（MVP）：本機檔案系統 MEDIA_ROOT/{tenant_id}/{YYYY-MM}/{media_id}{ext}
- env var：`MEDIA_ROOT`（預設 `./data/media`）
- 後續可換 GCS/S3，DB schema 不變
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.media_service")

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "./data/media")).resolve()
MAX_BYTES = 20 * 1024 * 1024  # 20 MiB

_ALLOWED_PURPOSES = {
    "door_check_before",
    "door_check_after",
    "completion_before",
    "completion_after",
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
}

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}

_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}


def _build_storage_path(*, tenant_id: str, media_id: str, content_type: str) -> Path:
    """產生 storage path：{tenant_id}/{YYYY-MM}/{media_id}{ext}"""
    yyyymm = datetime.now(timezone.utc).strftime("%Y-%m")
    ext = _EXT_BY_CT.get(content_type, "")
    rel = Path(tenant_id) / yyyymm / f"{media_id}{ext}"
    return rel


async def upload_media(
    *,
    tenant_id: str,
    uploader_user_id: str | None,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    purpose: str,
    work_order_id: str | None = None,
    dispute_id: str | None = None,
) -> dict:
    """驗證 → 寫檔到 FS → 寫 metadata 到 DB → 回傳含 url 的 dict。"""
    if purpose not in _ALLOWED_PURPOSES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"purpose must be one of {sorted(_ALLOWED_PURPOSES)}",
            422,
        )
    if not file_bytes:
        raise ApiError("VALIDATION_ERROR", "file is empty", 422)
    size = len(file_bytes)
    if size > MAX_BYTES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"file too large: {size} bytes > {MAX_BYTES} bytes",
            422,
        )
    ct = (content_type or "").lower()
    if ct not in _ALLOWED_CONTENT_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unsupported content_type '{content_type}'; expected one of {sorted(_ALLOWED_CONTENT_TYPES)}",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    media_id = str(uuid.uuid4())
    rel_path = _build_storage_path(
        tenant_id=tenant_id, media_id=media_id, content_type=ct
    )
    abs_path = MEDIA_ROOT / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        abs_path.write_bytes(file_bytes)
    except OSError as e:
        raise ApiError(
            "STORAGE_ERROR", f"failed to write file: {e}", 500
        ) from e

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    safe_filename = filename[:500] if filename else f"upload{_EXT_BY_CT.get(ct, '')}"

    cur = await db_module._conn.execute(
        "INSERT INTO media_files "
        "  (id, tenant_id, uploader_user_id, work_order_id, dispute_id, "
        "   purpose, filename, content_type, size_bytes, storage_path, sha256) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id, created_at",
        (
            media_id,
            tenant_id,
            uploader_user_id,
            work_order_id,
            dispute_id,
            purpose,
            safe_filename,
            ct,
            size,
            str(rel_path),
            sha256,
        ),
    )
    row = await cur.fetchone()

    return {
        "id": media_id,
        "url": f"/api/v1/media/{media_id}",
        "filename": safe_filename,
        "content_type": ct,
        "size_bytes": size,
        "purpose": purpose,
        "work_order_id": work_order_id,
        "dispute_id": dispute_id,
        "sha256": sha256,
        "created_at": (
            row[1].isoformat() if row and isinstance(row[1], datetime) else None
        ),
    }


async def get_media(*, tenant_id: str, media_id: str) -> tuple[bytes, str, str]:
    """讀檔。回傳 (bytes, content_type, filename)。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT storage_path, content_type, filename "
        "FROM media_files "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (media_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Media not found", 404)
    storage_path, ct, filename = row[0], row[1], row[2]
    abs_path = MEDIA_ROOT / storage_path
    try:
        data = abs_path.read_bytes()
    except FileNotFoundError as e:
        raise ApiError(
            "NOT_FOUND",
            f"Media file missing on storage: {storage_path}",
            404,
        ) from e
    return data, ct, filename


async def list_media_for_work_order(
    *, tenant_id: str, work_order_id: str
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, purpose, filename, content_type, size_bytes, created_at "
        "FROM media_files "
        "WHERE work_order_id = %s::uuid AND tenant_id = %s::uuid "
        "ORDER BY created_at DESC",
        (work_order_id, tenant_id),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "url": f"/api/v1/media/{r[0]}",
            "purpose": r[1],
            "filename": r[2],
            "content_type": r[3],
            "size_bytes": r[4],
            "created_at": (
                r[5].isoformat() if isinstance(r[5], datetime) else str(r[5])
            ),
        }
        for r in rows
    ]
    return {"items": items}


async def list_media_for_dispute(
    *, tenant_id: str, dispute_id: str
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, purpose, filename, content_type, size_bytes, created_at "
        "FROM media_files "
        "WHERE dispute_id = %s::uuid AND tenant_id = %s::uuid "
        "ORDER BY created_at DESC",
        (dispute_id, tenant_id),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "url": f"/api/v1/media/{r[0]}",
            "purpose": r[1],
            "filename": r[2],
            "content_type": r[3],
            "size_bytes": r[4],
            "created_at": (
                r[5].isoformat() if isinstance(r[5], datetime) else str(r[5])
            ),
        }
        for r in rows
    ]
    return {"items": items}
