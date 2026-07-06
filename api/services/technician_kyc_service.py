"""師傅 KYC 文件上傳與審核讀取 service(CR-0115 S-upload + S7)。

裁決依據:
  §8-2 (a) 兩階段上傳 —— 註冊建 pending 帳號時簽發一次性 upload token
      (48h 過期、次數上限、明文不落庫只存 SHA-256);憑 token 走公開端點
      上傳文件。師傅離開 pending_approval 後 token 即失效(核准前補件語意)。
  §8-3 (a) 平台管理員看全值+文件;預設讀取一律遮罩,全值走獨立 reveal
      端點並寫稽核。
  §8-7 檔案落本機 MEDIA_ROOT 的 kyc-registration/ 子樹(與 tenant media
      隔離;literal 目錄名不會與 tenant UUID 目錄衝突)。GCS 另 CR。

資料落點:兩張表皆在師傅身分權威庫(tech conn;fallback 單庫時即主庫),
不落品牌庫(§8-1 最小揭露)。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import core.db as db_module
from core.errors import ApiError
from core.pii_crypto import decrypt_pii
from services.media_service import MEDIA_ROOT

logger = logging.getLogger("api.technician_kyc_service")

# Tier 3 文件類型(CR-0115 §1:身分證正反面/證照掃描/保險證明或良民證)
ALLOWED_DOC_TYPES = ("id_front", "id_back", "license", "insurance")

TOKEN_TTL_HOURS = 48
MAX_DOC_BYTES = 10 * 1024 * 1024  # 10 MiB(證件照/掃描檔;小於一般 media 上限)

# KYC 專屬型別白名單(比一般 media 窄:不收 HEIC —— 瀏覽器 <img> 無法解碼,
# 審核頁無從預覽;前端 accept 不含 heic 時 iPhone 會自動轉 JPEG)。
# 附 magic bytes 前綴:公開端點不可信任 client 自報 Content-Type,入庫前驗檔頭。
_KYC_CONTENT_TYPES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/jpg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),  # RIFF....WEBP(offset 8 另驗)
    "application/pdf": (b"%PDF-",),
}
_KYC_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

# 公開端點 per-IP 限流(in-memory,單實例;多 replica 失準已記 CR-0114 已知取捨)
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX_UPLOADS = 30
_rate_buckets: dict[str, deque[float]] = {}


def rate_limit_check(client_ip: str | None) -> None:
    """同 IP 15 分鐘內最多 30 次上傳;超過 → 429。無 IP(測試)不擋。

    公開給 router 在讀取 request body **之前**呼叫(先擋量再耗資源)。
    """
    if not client_ip:
        return
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(client_ip, deque())
    while bucket and now - bucket[0] > _RATE_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX_UPLOADS:
        raise ApiError("RATE_LIMITED", "上傳過於頻繁,請稍後再試", 429)
    bucket.append(now)


def _validate_file_signature(ct: str, file_bytes: bytes) -> None:
    """驗 magic bytes 與宣告型別一致;不符 → 422(擋偽造 Content-Type 上傳)。"""
    prefixes = _KYC_CONTENT_TYPES[ct]
    if not any(file_bytes.startswith(p) for p in prefixes):
        raise ApiError("VALIDATION_ERROR", "檔案內容與宣告型別不符", 422)
    if ct == "image/webp" and file_bytes[8:12] != b"WEBP":
        raise ApiError("VALIDATION_ERROR", "檔案內容與宣告型別不符", 422)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_upload_token(conn: Any, *, technician_id: str) -> dict:
    """簽發兩階段上傳 token(§8-2a)。回 {token, expires_at};明文只出現在
    註冊 response,落庫僅 SHA-256。"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    await conn.execute(
        "INSERT INTO technician_upload_token (technician_id, token_hash, expires_at) "
        "VALUES (%s::uuid, %s, %s)",
        (technician_id, _hash_token(token), expires_at),
    )
    return {"token": token, "expires_at": expires_at.isoformat()}


async def _resolve_token(conn: Any, token: str) -> tuple[str, str, str]:
    """驗 token → (token_id, technician_id, tenant_id)。

    不合法/過期/超次數/師傅已離開 pending_approval → 403(單一錯誤碼,
    不區分原因,避免探測)。
    """
    cur = await conn.execute(
        "SELECT ut.id, ut.technician_id, ut.expires_at, ut.upload_count, ut.max_uploads, "
        "       t.status, t.tenant_id "
        "FROM technician_upload_token ut "
        "JOIN technicians t ON t.id = ut.technician_id "
        "WHERE ut.token_hash = %s",
        (_hash_token(token),),
    )
    row = await cur.fetchone()
    invalid = ApiError("UPLOAD_TOKEN_INVALID", "上傳連結無效或已過期,請聯絡平台協助補件", 403)
    if not row:
        raise invalid
    token_id, technician_id, expires_at, upload_count, max_uploads, status, tenant_id = row
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        raise invalid
    # 次數上限這裡只做快速拒絕;實際消耗走 _claim_upload_slot 的原子遞增
    # (check-then-act 在並發下可被突破,不能作為 gate)。
    if upload_count >= max_uploads:
        raise invalid
    # 核准前補件語意:離開 pending_approval(已核准/已拒絕/…)即不可再上傳
    if status != "pending_approval":
        raise invalid
    return str(token_id), str(technician_id), str(tenant_id)


async def _claim_upload_slot(conn: Any, token_id: str) -> None:
    """原子消耗一次上傳額度:UPDATE 帶 upload_count < max_uploads 條件,
    並發下不可能超額;無列可更新 → 403。"""
    cur = await conn.execute(
        "UPDATE technician_upload_token "
        "SET upload_count = upload_count + 1, last_used_at = NOW() "
        "WHERE id = %s::uuid AND upload_count < max_uploads "
        "RETURNING id",
        (token_id,),
    )
    if not await cur.fetchone():
        raise ApiError("UPLOAD_TOKEN_INVALID", "上傳連結無效或已過期,請聯絡平台協助補件", 403)


async def upload_registration_document(
    *,
    token: str,
    doc_type: str,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    client_ip: str | None = None,
) -> dict:
    """公開端點主流程:限流 → 驗檔 → 驗 token → 原子扣額度 → 寫檔 + metadata。

    落 tech conn(師傅身分域)。router 已先限流並以 MAX_DOC_BYTES+1 截讀,
    此處 client_ip 傳 None 時不重複計數(直接呼叫本函式的路徑仍可自帶 IP)。
    """
    rate_limit_check(client_ip)

    if doc_type not in ALLOWED_DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of {sorted(ALLOWED_DOC_TYPES)}",
            422,
        )
    if not file_bytes:
        raise ApiError("VALIDATION_ERROR", "file is empty", 422)
    if len(file_bytes) > MAX_DOC_BYTES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"file too large: > {MAX_DOC_BYTES} bytes",
            422,
        )
    ct = (content_type or "").lower()
    if ct not in _KYC_CONTENT_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unsupported content_type '{content_type}'; expected one of {sorted(_KYC_CONTENT_TYPES)}",
            422,
        )
    _validate_file_signature(ct, file_bytes)

    conn = await db_module.require_tech_conn()
    token_id, technician_id, tenant_id = await _resolve_token(conn, token)

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    # 同師傅同槽位同檔重傳 → 回既有列(斷線重試 idempotent)。dedup key 含
    # doc_type:同一張檔案傳到不同槽位是不同文件宣告,必須各自入庫,否則
    # 第二個槽位會假成功(前端顯示 ✓ 但審核頁看不到該類文件)。
    cur = await conn.execute(
        "SELECT id, doc_type, filename, size_bytes, created_at "
        "FROM technician_registration_document "
        "WHERE technician_id = %s::uuid AND sha256 = %s AND doc_type = %s LIMIT 1",
        (technician_id, sha256, doc_type),
    )
    existing = await cur.fetchone()
    if existing:
        return {
            "id": str(existing[0]),
            "doc_type": existing[1],
            "filename": existing[2],
            "size_bytes": existing[3],
            "created_at": existing[4].isoformat() if existing[4] else None,
            "deduplicated": True,
        }

    # 原子消耗上傳額度(並發安全);之後才寫檔 + 入庫。
    await _claim_upload_slot(conn, token_id)

    doc_id = str(uuid.uuid4())
    ext = _KYC_EXT_BY_CT.get(ct, "")
    rel_path = f"kyc-registration/{technician_id}/{doc_id}{ext}"
    abs_path = MEDIA_ROOT / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        abs_path.write_bytes(file_bytes)
    except OSError as e:
        raise ApiError("STORAGE_ERROR", f"failed to write file: {e}", 500) from e

    safe_filename = filename[:500] if filename else f"document{ext}"
    try:
        await conn.execute(
            "INSERT INTO technician_registration_document "
            "  (id, technician_id, tenant_id, doc_type, filename, content_type, "
            "   size_bytes, storage_path, sha256) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)",
            (
                doc_id, technician_id, tenant_id, doc_type, safe_filename,
                ct, len(file_bytes), rel_path, sha256,
            ),
        )
    except Exception:
        # metadata 入庫失敗 → 清掉剛寫的檔案,不留孤兒(額度已耗屬可接受損耗)
        abs_path.unlink(missing_ok=True)
        raise

    return {
        "id": doc_id,
        "doc_type": doc_type,
        "filename": safe_filename,
        "size_bytes": len(file_bytes),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── S7 審核讀取面(platform console;gate 由 router require_platform_admin)──


async def get_kyc_review(*, technician_id: str) -> dict:
    """審核頁一次取:Tier 1 補充欄位 + Tier 2 遮罩 KYC + 文件清單。

    預設一律遮罩(§8-3);全值走 reveal_kyc() 並寫稽核。
    """
    conn = await db_module.require_tech_conn()

    cur = await conn.execute(
        "SELECT years_experience, bio, vehicle_type, availability_note, "
        "       emergency_contact_name, emergency_contact_phone, terms_accepted_at "
        "FROM technicians WHERE id = %s::uuid",
        (technician_id,),
    )
    tech = await cur.fetchone()
    if not tech:
        raise ApiError("TECHNICIAN_NOT_FOUND", "Technician not found", 404)
    profile = {
        "years_experience": tech[0],
        "bio": tech[1],
        "vehicle_type": tech[2],
        "availability_note": tech[3],
        "emergency_contact_name": tech[4],
        "emergency_contact_phone": tech[5],
        "terms_accepted_at": tech[6].isoformat() if tech[6] else None,
    }

    cur = await conn.execute(
        "SELECT national_id_enc IS NOT NULL, national_id_last3, bank_code, "
        "       bank_account_enc IS NOT NULL, bank_account_last4, "
        "       birth_date, address, tax_id "
        "FROM technician_kyc WHERE technician_id = %s::uuid",
        (technician_id,),
    )
    krow = await cur.fetchone()
    kyc = None
    if krow:
        kyc = {
            "has_national_id": bool(krow[0]),
            "national_id_last3": krow[1],
            "bank_code": krow[2],
            "has_bank_account": bool(krow[3]),
            "bank_account_last4": krow[4],
            "birth_date": krow[5].isoformat() if krow[5] else None,
            "address": krow[6],
            "tax_id": krow[7],
        }

    cur = await conn.execute(
        "SELECT id, doc_type, filename, content_type, size_bytes, created_at "
        "FROM technician_registration_document "
        "WHERE technician_id = %s::uuid ORDER BY created_at",
        (technician_id,),
    )
    documents = [
        {
            "id": str(r[0]),
            "doc_type": r[1],
            "filename": r[2],
            "content_type": r[3],
            "size_bytes": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in await cur.fetchall()
    ]

    return {"profile": profile, "kyc": kyc, "documents": documents}


async def reveal_kyc(
    *, technician_id: str, actor_user_id: str | None
) -> dict:
    """解密回傳敏感 PII 全值(§8-3:僅平台管理員;gate 在 router)。

    每次揭露寫 `saas.technician_lifecycle_event`(tech conn)—— 不用品牌庫
    audit_events:其 actor_id FK 指品牌庫 users,平台管理員帳號在平台庫會
    FK violation;且 N 品牌拓撲下平台層稽核不該落在單一品牌庫。lifecycle
    audit 表 actor 無 FK、已有平台管理員寫入前例(CR-0114 R3),並讓揭露
    紀錄直接出現在審核頁的生命週期歷史。

    **fail-closed**:稽核寫不進去就不回傳全值(§8-3 揭露必留痕;fail-soft
    會讓遮罩形同虛設 —— 稽核壞掉期間可無痕撈 PII)。
    """
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT k.national_id_enc, k.bank_account_enc, t.tenant_id "
        "FROM technician_kyc k JOIN technicians t ON t.id = k.technician_id "
        "WHERE k.technician_id = %s::uuid",
        (technician_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("KYC_NOT_FOUND", "此師傅未提供 KYC 敏感資料", 404)

    try:
        await conn.execute(
            "INSERT INTO saas.technician_lifecycle_event "
            "  (tenant_id, technician_id, event_type, reason, actor_user_id, actor_role) "
            "VALUES (%s::uuid, %s::uuid, 'kyc_reveal', "
            "        '平台管理員檢視 KYC 敏感資料全值(national_id/bank_account)', "
            "        %s::uuid, 'platform_admin')",
            (str(row[2]), technician_id, actor_user_id),
        )
    except Exception as e:
        logger.error("KYC reveal 稽核寫入失敗,拒絕揭露(fail-closed)", exc_info=True)
        raise ApiError(
            "AUDIT_WRITE_FAILED", "稽核寫入失敗,暫時無法顯示完整資料", 500
        ) from e

    return {
        "national_id": decrypt_pii(row[0]),
        "bank_account": decrypt_pii(row[1]),
    }


async def get_document_file(
    *, technician_id: str, document_id: str
) -> tuple[bytes, str, str]:
    """讀文件實體(platform 審核檢視)。回 (bytes, content_type, filename)。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT storage_path, content_type, filename "
        "FROM technician_registration_document "
        "WHERE id = %s::uuid AND technician_id = %s::uuid",
        (document_id, technician_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Document not found", 404)
    storage_path, ct, filename = row
    abs_path = MEDIA_ROOT / storage_path
    try:
        data = abs_path.read_bytes()
    except FileNotFoundError as e:
        raise ApiError(
            "NOT_FOUND", f"Document file missing on storage: {storage_path}", 404
        ) from e
    return data, ct, filename or "document"
