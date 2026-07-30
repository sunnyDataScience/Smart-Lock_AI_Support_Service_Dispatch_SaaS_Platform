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
    "completion_during",   # CR-0054：施工中拓孔結構照（PDF §四 施工前/中/後三類）
    "completion_after",
    "completion_signature",  # 技師完工客戶簽名（前端 my-orders/[id] 簽名上傳用）
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
}

# CR-0194（UAT-D-002 業主裁決選項 2）：移除 image/heic ＋ 加 magic bytes 驗證。
#
# WHY 移除 HEIC：瀏覽器 <img> 無法解碼 HEIC，品牌端審核完工證據時只看到破圖，
# 而完工硬閘仍算「有照片」＝閘門過了、證據看不到。前端 accept 已收窄（iPhone
# 會自動轉 JPEG），但 accept 只是提示不是強制——桌機仍可用「所有檔案」選 .heic，
# 所以伺服器端白名單才是真正的閘。
#
# WHY 同時要 magic bytes：光移除白名單擋不住「把 Content-Type 謊報成 image/jpeg
# 再上傳 HEIC bytes」。那種檔案會以 .jpg 落盤、DB 記 image/jpeg，瀏覽器一樣解不開，
# 但這次連「為什麼壞」都查不出來——等於把可見問題換成不可見問題。驗檔頭才真的關上。
# 前綴表與 technician_kyc_service._KYC_CONTENT_TYPES 刻意保持一致做法。
_ALLOWED_CONTENT_TYPES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/jpg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),  # RIFF....WEBP（offset 8 另驗）
    "application/pdf": (b"%PDF-",),
}

_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def _validate_file_signature(ct: str, file_bytes: bytes) -> None:
    """驗 magic bytes 與宣告型別一致；不符 → 422。

    HEIC 沒有自己的分支是刻意的：它已不在白名單，宣告 heic 會先被型別檢查擋掉；
    謊報成 jpeg/png 的 HEIC 則會在這裡因檔頭不符被擋（HEIC 檔頭是
    `....ftypheic` 之類，不會以 FFD8FF 或 PNG 簽章開頭）。
    """
    prefixes = _ALLOWED_CONTENT_TYPES.get(ct)
    if prefixes is None:
        # fail-closed：呼叫端理應已先驗白名單，但若順序被改動，這裡不可讓
        # KeyError 逃成 500——未知型別一律當不合法。
        raise ApiError("VALIDATION_ERROR", f"unsupported content_type '{ct}'", 422)
    if not any(file_bytes.startswith(p) for p in prefixes):
        raise ApiError(
            "VALIDATION_ERROR",
            f"檔案內容與宣告型別 '{ct}' 不符（可能是改了副檔名或 HEIC 原檔）",
            422,
        )
    if ct == "image/webp" and file_bytes[8:12] != b"WEBP":
        raise ApiError("VALIDATION_ERROR", "檔案內容與宣告型別不符", 422)


def _build_storage_path(*, tenant_id: str, media_id: str, content_type: str) -> Path:
    """產生 storage path：{tenant_id}/{YYYY-MM}/{media_id}{ext}"""
    yyyymm = datetime.now(timezone.utc).strftime("%Y-%m")
    ext = _EXT_BY_CT.get(content_type, "")
    rel = Path(tenant_id) / yyyymm / f"{media_id}{ext}"
    return rel


# ── CR-0040 Evidence 角色可見性（BR-M09-02 / Q026；規則式過濾，HD-1，不加欄位）──────
# 客戶家中環境照 = 門檢照 + 完工前照。品牌不可看（隱私）；會計只需完工/付款必要照。
# 其餘內部 staff（admin/ops/dispatcher/customer_service/technician）看全部。
_ENV_PURPOSES = ("door_check_before", "door_check_after", "completion_before", "completion_during")
_HIDDEN_PURPOSES_BY_ROLE = {
    "brand_oem": set(_ENV_PURPOSES),                          # 品牌：不看客戶家中環境照
    "brand": set(_ENV_PURPOSES),                              # 角色別名相容
    "accounting": {"door_check_before", "door_check_after"},  # 會計：完工/付款必要照即可
}


def _hidden_purposes(role: str | None) -> set[str]:
    """該角色看不到的 media purpose 集合（空集 = 看全部，即內部 staff）。"""
    return _HIDDEN_PURPOSES_BY_ROLE.get((role or "").lower(), set())


async def soft_delete_expired_media() -> int:
    """CR-0040 清除 cron（HD-4 軟刪）：retention_until 過期且未軟刪的 media 標 deleted_at。回筆數。

    CR-0067 / TI-M09-03：legal_hold=true（法務保留）即使過期也不刪（legal_hold wins）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE media_files SET deleted_at = NOW() "
        "WHERE retention_until IS NOT NULL AND retention_until < NOW() "
        "  AND deleted_at IS NULL "
        "  AND legal_hold IS NOT TRUE "
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
    # CR-0194：client 自報的 Content-Type 不可信，驗檔頭（見 _validate_file_signature）
    _validate_file_signature(ct, file_bytes)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    media_id = str(uuid.uuid4())
    rel_path = _build_storage_path(
        tenant_id=tenant_id, media_id=media_id, content_type=ct
    )
    abs_path = MEDIA_ROOT / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    # FR-API-08：證據位元組 envelope 加密後落盤（sha256 仍算明文，見下）。
    from core import media_crypto
    try:
        abs_path.write_bytes(media_crypto.encrypt_bytes(file_bytes))
    except OSError as e:
        raise ApiError(
            "STORAGE_ERROR", f"failed to write file: {e}", 500
        ) from e

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    safe_filename = filename[:500] if filename else f"upload{_EXT_BY_CT.get(ct, '')}"

    # 保存期：RMA 證據（客訴 dispute / 保固 warranty WO）3 年；其餘 1 年。
    # CR-0164 F#6（衝突②裁定）：NFR-Priv-003/Aud-003（合約下限）+ R-F4 紅線＝RMA +3 年
    # 為正典，推翻 Q027 的 2 年（Q027 無文件出處）。
    ret_years = 3 if purpose.startswith("dispute_evidence") else 1
    if ret_years == 1 and work_order_id:
        wcur = await db_module._conn.execute(
            "SELECT 1 FROM work_orders WHERE id = %s::uuid "
            "  AND service_category IN ('warranty_in', 'warranty_out')",
            (work_order_id,),
        )
        if await wcur.fetchone():
            ret_years = 3

    # CR-0064 / TI-M09-01：sha256 去重 — 同 WO 同檔二次上傳回既有，不重複入庫（idempotent）。
    if work_order_id:
        ex = await db_module._conn.execute(
            "SELECT id, filename, content_type, size_bytes, purpose, sha256, created_at "
            "FROM media_files WHERE work_order_id = %s::uuid AND sha256 = %s "
            "  AND deleted_at IS NULL LIMIT 1",
            (work_order_id, sha256),
        )
        exr = await ex.fetchone()
        if exr:
            return {
                "id": str(exr[0]), "url": f"/api/v1/media/{exr[0]}", "filename": exr[1],
                "content_type": exr[2], "size_bytes": exr[3], "purpose": exr[4],
                "work_order_id": work_order_id, "dispute_id": dispute_id, "sha256": exr[5],
                "created_at": exr[6].isoformat() if exr[6] else None, "deduplicated": True,
            }

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
    # FR-API-08：解密回明文；dual-read——舊明文檔（非本金鑰 token）→ 回原位元組。
    from core import media_crypto
    data = media_crypto.decrypt_bytes(data) or data
    return data, ct, filename


async def list_media_for_work_order(
    *, tenant_id: str, work_order_id: str, role: str | None = None
) -> dict:
    """列工單媒體。CR-0040：依角色過濾不可見 purpose（品牌不看環境照）+ 排除軟刪。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    hidden = _hidden_purposes(role)
    sql = (
        "SELECT id, purpose, filename, content_type, size_bytes, created_at, legal_hold "
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
            "legal_hold": bool(r[6]),  # CR-0109：法務保留旗標（true=不被 retention cron 清）
        }
        for r in rows
    ]
    return {"items": items}


async def set_legal_hold(
    *, tenant_id: str, media_id: str, hold: bool,
    reason: str | None = None, actor_id: str | None = None, actor_role: str | None = None,
) -> dict:
    """CR-0109：手動設定/解除媒體法務保留（legal_hold）。

    legal_hold=true → retention cron 不軟刪（爭議/保固/訴訟期間鎖證據，legal_hold wins）。
    手動 admin/主管操作（自動觸發/解除規則待業主定義，本輪僅手動）。寫稽核軌跡。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE media_files SET legal_hold = %s "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL "
        "RETURNING id, work_order_id, purpose, legal_hold",
        (hold, media_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("MEDIA_NOT_FOUND", "Media not found in this tenant", 404)

    from services import audit_log_service
    await audit_log_service.log_event(
        event_type="media_legal_hold",
        actor_id=actor_id,
        actor_role=actor_role,
        action="set_legal_hold" if hold else "release_legal_hold",
        target_type="media_file",
        target_id=media_id,
        payload={"legal_hold": hold, "reason": reason, "work_order_id": str(row[1]) if row[1] else None},
    )
    return {"data": {"id": str(row[0]), "legal_hold": bool(row[3])}}


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
