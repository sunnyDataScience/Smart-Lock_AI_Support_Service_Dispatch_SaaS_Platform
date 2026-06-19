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


# ── CR-0040 Evidence 角色可見性（BR-M09-02 / Q026；規則式過濾，HD-1，不加欄位）──────
# 客戶家中環境照 = 門檢照 + 完工前照。品牌不可看（隱私）；會計只需完工/付款必要照。
# 其餘內部 staff（admin/ops/dispatcher/customer_service/technician）看全部。
_ENV_PURPOSES = ("door_check_before", "door_check_after", "completion_before")
_HIDDEN_PURPOSES_BY_ROLE = {
    "brand_oem": set(_ENV_PURPOSES),                          # 品牌：不看客戶家中環境照
    "brand": set(_ENV_PURPOSES),                              # 角色別名相容
    "accounting": {"door_check_before", "door_check_after"},  # 會計：完工/付款必要照即可
}


def _hidden_purposes(role: str | None) -> set[str]:
    """該角色看不到的 media purpose 集合（空集 = 看全部，即內部 staff）。"""
    return _HIDDEN_PURPOSES_BY_ROLE.get((role or "").lower(), set())


async def soft_delete_expired_media() -> int:
    """CR-0040 清除 cron（HD-4 軟刪）：retention_until 過期且未軟刪的 media 標 deleted_at。回筆數。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE media_files SET deleted_at = NOW() "
        "WHERE retention_until IS NOT NULL AND retention_until < NOW() "
        "  AND deleted_at IS NULL "
        "RETURNING id"
    )
    rows = await cur.fetchall()
    return len(rows)


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

    # CR-0040 保存期（Q027）：客訴(dispute) 2 年；保固案（warranty WO）2 年；其餘 1 年。
    ret_years = 2 if purpose.startswith("dispute_evidence") else 1
    if ret_years == 1 and work_order_id:
        wcur = await db_module._conn.execute(
            "SELECT 1 FROM work_orders WHERE id = %s::uuid "
            "  AND service_category IN ('warranty_in', 'warranty_out')",
            (work_order_id,),
        )
        if await wcur.fetchone():
            ret_years = 2

    cur = await db_module._conn.execute(
        "INSERT INTO media_files "
        "  (id, tenant_id, uploader_user_id, work_order_id, dispute_id, "
        "   purpose, filename, content_type, size_bytes, storage_path, sha256, "
        "   retention_until) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "        NOW() + make_interval(years => %s)) "
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
            ret_years,
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


async def get_media(
    *, tenant_id: str, media_id: str, role: str | None = None
) -> tuple[bytes, str, str]:
    """讀檔。回傳 (bytes, content_type, filename)。

    CR-0040：角色不可見的 purpose（如品牌看環境照）→ 404（不洩漏存在性）；軟刪 → 404。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT storage_path, content_type, filename, purpose "
        "FROM media_files "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL",
        (media_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Media not found", 404)
    storage_path, ct, filename, purpose = row[0], row[1], row[2], row[3]
    # CR-0040 角色可見性：不可見 → 404（避免向品牌洩漏該照存在）
    if purpose in _hidden_purposes(role):
        raise ApiError("NOT_FOUND", "Media not found", 404)
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
    *, tenant_id: str, work_order_id: str, role: str | None = None
) -> dict:
    """列工單媒體。CR-0040：依角色過濾不可見 purpose（品牌不看環境照）+ 排除軟刪。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    hidden = _hidden_purposes(role)
    sql = (
        "SELECT id, purpose, filename, content_type, size_bytes, created_at "
        "FROM media_files "
        "WHERE work_order_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND deleted_at IS NULL "
    )
    params: list = [work_order_id, tenant_id]
    if hidden:
        sql += "  AND purpose <> ALL(%s) "
        params.append(list(hidden))
    sql += "ORDER BY created_at DESC"
    cur = await db_module._conn.execute(sql, params)
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
