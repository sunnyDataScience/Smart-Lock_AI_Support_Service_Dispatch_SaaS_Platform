"""Knowledge Base Manuals 業務邏輯。

範圍：listManuals（cursor + limit + brand 篩選）+ deleteManual。
不含：upload / chunk 內容查詢（待 PDF 解析模組接入）。

DB↔OpenAPI 欄位對齊：
  - filename (DB)        → file_name (API)
  - title   (DB, 可 NULL) → title (API, required)；NULL → 用 filename 去除副檔名 fallback
  - status (4-value)     → ManualStatus (3-value)：
      processing → processing
      indexing   → processing  （索引中對前端來說仍是處理中）
      completed  → ready
      failed     → failed
  - total_chunks (DB)    → chunk_count (API)
"""

from __future__ import annotations

import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.manual_service")


_DB_STATUS_TO_API = {
    "processing": "processing",
    "indexing": "processing",
    "completed": "ready",
    "failed": "failed",
}


_SELECT_COLUMNS = (
    "id, title, brand, model, filename, "
    "COALESCE(file_size_bytes, 0) AS file_size_bytes, "
    "status, total_chunks, created_at"
)


def _filename_to_title(filename: str | None) -> str:
    if not filename:
        return ""
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)
    return name or base


def _row_to_dict(row: tuple) -> dict:
    db_status = (row[6] or "processing").lower()
    api_status = _DB_STATUS_TO_API.get(db_status, "processing")
    title = row[1] or _filename_to_title(row[4])
    return {
        "id": str(row[0]),
        "title": title,
        "brand": row[2] or "",
        "model": row[3],
        "file_name": row[4] or "",
        "file_size_bytes": int(row[5] or 0),
        "status": api_status,
        "chunk_count": int(row[7]) if row[7] is not None else None,
        "created_at": row[8].isoformat() if row[8] else None,
    }


async def list_manuals(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    brand: str | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "deleted_at IS NULL"]  # CR-0005 HD-02 軟刪過濾
    args: list = [tenant_id]

    if brand:
        where.append("brand = %s")
        args.append(brand)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM manuals "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY created_at DESC, id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[8].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",  # 部分瀏覽器/curl 不帶正確 mime
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB；對齊一般 PDF 手冊上限


async def upload_manual(
    *,
    tenant_id: str,
    uploader_user_id: str | None,
    filename: str,
    content_type: str | None,
    file_bytes: bytes,
    brand: str,
    title: str,
    model: str | None = None,
) -> dict:
    """uploadManual — 收檔後 INSERT manuals 一筆並回 202。

    範圍（MVP）：
      - 不真的解析 PDF / 不切 chunks / 不算 vector embedding（pipeline 模組 ownership）
      - 僅做 size + content-type + 必填驗證 → INSERT manuals (status='processing')
      - file 內容暫不持久化（本 phase 不引入 GCS / 檔案系統依賴），實際解析由
        pipeline 從外部存儲讀取；本端點只負責建立 metadata 並回 manual_id
      - 後續 pipeline 完成後會 UPDATE manuals SET status='completed', total_chunks=N
    """
    # ── 必填驗證 ──
    if not brand or not brand.strip():
        raise ApiError("VALIDATION_ERROR", "brand is required", 422)
    if not title or not title.strip():
        raise ApiError("VALIDATION_ERROR", "title is required", 422)
    if not filename:
        raise ApiError("VALIDATION_ERROR", "file is required", 422)

    if len(title) > 200:
        raise ApiError("VALIDATION_ERROR", "title must be at most 200 chars", 422)
    if len(brand) > 100:
        raise ApiError("VALIDATION_ERROR", "brand must be at most 100 chars", 422)
    if model is not None and len(model) > 100:
        raise ApiError("VALIDATION_ERROR", "model must be at most 100 chars", 422)

    # ── 檔案驗證 ──
    size = len(file_bytes)
    if size == 0:
        raise ApiError("VALIDATION_ERROR", "file is empty", 422)
    if size > _MAX_UPLOAD_BYTES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"file too large: {size} bytes > {_MAX_UPLOAD_BYTES} bytes",
            422,
        )
    ct = (content_type or "").lower()
    # 檔名 .pdf 結尾或 mime 命中皆放行（瀏覽器 mime 不一致時退一步用副檔名）
    if not (
        ct in _ALLOWED_CONTENT_TYPES
        or filename.lower().endswith(".pdf")
    ):
        raise ApiError(
            "VALIDATION_ERROR",
            f"unsupported content_type '{content_type}'; expected application/pdf",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # ── INSERT manuals ──
    cur = await db_module._conn.execute(
        "INSERT INTO manuals "
        "  (tenant_id, filename, brand, model, file_size_bytes, "
        "   total_chunks, status, uploaded_by, title) "
        "VALUES (%s::uuid, %s, %s, %s, %s, 0, 'processing', %s, %s) "
        f"RETURNING {_SELECT_COLUMNS}",
        (
            tenant_id,
            filename[:255],
            brand.strip()[:100],
            (model.strip() if model else None),
            size,
            uploader_user_id,
            title.strip()[:200],
        ),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("DB_ERROR", "Failed to create manual record", 500)
    return _row_to_dict(row)


async def delete_manual(*, tenant_id: str, manual_id: str) -> None:
    """刪除手冊（含 manual_chunks 透過 FK ON DELETE CASCADE 同步清除）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT id FROM manuals WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (manual_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", f"Manual {manual_id} not found", 404)

    await db_module._conn.execute(
        "DELETE FROM manuals WHERE id = %s::uuid",
        (manual_id,),
    )
