"""CR-0176：per-subject DEK 生命週期服務（registry-backed，接 envelope crypto）。

FR-API-16 / NFR-Priv-008。搭配 `core.dek_crypto`（純密碼學）與 `saas.data_encryption_key`
registry（migration 112）：

- get_or_create_active_dek：取該 subject 的 active DEK（cache→registry→新建 wrap 落庫）。
- encrypt_pii / decrypt_pii：對單一 PII 值用該 subject 的 DEK 加解密。decrypt **不建** DEK
  ——已銷毀（無 active DEK）→ 回 None（＝crypto-shred 後不可讀）。
- destroy_dek（HD-4 tombstone）：registry status→destroyed、wrapped_dek 清空、destroyed_at
  蓋章（row 保留供稽核），並逐出 cache → 該 subject 全部密文瞬間不可解，**不影響他人**。

cache（HD-7）：ContextVar 請求域字典，各 request task 天然隔離；destroy 立即逐出當前域。
registry 存取集中在 `_load_wrapped` / `_store_wrapped` / `_mark_destroyed` 三個內部函式，
便於單元測試以 in-memory stub monkeypatch（證明 shred 全流程不需真 DB）。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

import core.db as db_module
from core import dek_crypto

logger = logging.getLogger(__name__)

_dek_cache_var: ContextVar[dict | None] = ContextVar("dek_cache", default=None)


def _cache() -> dict:
    c = _dek_cache_var.get()
    if c is None:
        c = {}
        _dek_cache_var.set(c)
    return c


# ── registry 存取（可 monkeypatch）────────────────────────────────────────
async def _load_wrapped(subject_user_id: str) -> str | None:
    """讀該 subject 的 active wrapped DEK；無 active（含已銷毀）→ None。"""
    cur = await db_module._conn.execute(
        "SELECT wrapped_dek FROM saas.data_encryption_key "
        "WHERE subject_user_id = %s::uuid AND status = 'active'",
        (subject_user_id,),
    )
    row = await cur.fetchone()
    return row[0] if row and row[0] else None


async def _store_wrapped(subject_user_id: str, tenant_id: str | None, wrapped: str) -> None:
    """新建 active DEK 記錄。撞既有 active（併發）→ DO NOTHING（由呼叫端重讀）。"""
    await db_module._conn.execute(
        "INSERT INTO saas.data_encryption_key "
        "  (subject_user_id, tenant_id, wrapped_dek, status) "
        "VALUES (%s::uuid, %s, %s, 'active') "
        "ON CONFLICT (subject_user_id) WHERE status = 'active' DO NOTHING",
        (subject_user_id, tenant_id, wrapped),
    )


async def _mark_destroyed(subject_user_id: str, actor_user_id: str | None) -> bool:
    """HD-4 tombstone：active→destroyed、清空金鑰材料、蓋銷毀章。回是否有 active DEK 被銷毀。"""
    cur = await db_module._conn.execute(
        "UPDATE saas.data_encryption_key SET "
        "  status = 'destroyed', wrapped_dek = NULL, "
        "  destroyed_at = NOW(), destroyed_by = %s::uuid, updated_at = NOW() "
        "WHERE subject_user_id = %s::uuid AND status = 'active' "
        "RETURNING id",
        (actor_user_id, subject_user_id),
    )
    return bool(await cur.fetchone())


# ── 公開 API ───────────────────────────────────────────────────────────────
async def get_or_create_active_dek(subject_user_id: str, tenant_id: str | None = None) -> bytes:
    """取（或建）該 subject 的 active DEK 材料（unwrapped bytes）。"""
    cache = _cache()
    if subject_user_id in cache:
        return cache[subject_user_id]

    wrapped = await _load_wrapped(subject_user_id)
    if wrapped:
        dek = dek_crypto.unwrap_dek(wrapped)
        if dek is not None:
            cache[subject_user_id] = dek
            return dek
        # wrapped 存在但 KEK 解不開＝金鑰不符/毀損：不靜默新建（會孤立既有密文），拋出。
        raise RuntimeError("existing wrapped DEK 無法以現行 KEK 還原（金鑰不符？見 CIA §10 R2）")

    dek = dek_crypto.generate_dek()
    await _store_wrapped(subject_user_id, tenant_id, dek_crypto.wrap_dek(dek))
    # 併發下他人可能先建 → 重讀確保用 registry 權威那把
    wrapped2 = await _load_wrapped(subject_user_id)
    if wrapped2:
        authoritative = dek_crypto.unwrap_dek(wrapped2)
        if authoritative is not None:
            dek = authoritative
    cache[subject_user_id] = dek
    return dek


async def _get_active_dek(subject_user_id: str) -> bytes | None:
    """取 active DEK；已銷毀/不存在 → None（decrypt 專用，**不建**）。"""
    cache = _cache()
    if subject_user_id in cache:
        return cache[subject_user_id]
    dek = dek_crypto.unwrap_dek(await _load_wrapped(subject_user_id))
    if dek is not None:
        cache[subject_user_id] = dek
    return dek


async def encrypt_pii(subject_user_id: str, tenant_id: str | None, plaintext: str | None) -> str | None:
    """用該 subject 的 DEK 加密單一 PII 值。None/空 → None。"""
    if plaintext is None or (isinstance(plaintext, str) and plaintext.strip() == ""):
        return None
    dek = await get_or_create_active_dek(subject_user_id, tenant_id)
    return dek_crypto.encrypt_with_dek(dek, plaintext)


async def decrypt_pii(subject_user_id: str, ciphertext: str | None) -> str | None:
    """用該 subject 的 active DEK 解密。DEK 已銷毀（crypto-shred）→ None（不可讀）。"""
    if not ciphertext:
        return None
    return dek_crypto.decrypt_with_dek(await _get_active_dek(subject_user_id), ciphertext)


async def destroy_dek(subject_user_id: str, actor_user_id: str | None = None) -> bool:
    """crypto-shred：銷毀該 subject 的 active DEK（tombstone）並逐出 cache。
    回是否確有 active DEK 被銷毀（無則 no-op，例：該 subject 尚無加密 PII）。"""
    destroyed = await _mark_destroyed(subject_user_id, actor_user_id)
    _cache().pop(subject_user_id, None)
    if destroyed:
        logger.info("crypto-shred: DEK destroyed for subject=%s", subject_user_id)
    return destroyed


# ── CR-0176 S2：品牌庫 users PII 欄位 dual-write / dual-read ───────────────
# 範圍＝CIA HD-2 phase 1：users 三欄（migration 112 已備妥對應 *_enc 欄）。
# work_orders 客戶欄（phase 2）與技師/平台庫 users（ADR-020 三庫）為範圍延伸。
USER_PII_FIELDS: dict[str, str] = {
    "display_name": "display_name_enc",
    "email": "email_enc",
    "phone": "phone_enc",
}
# S5 前置（業主 0722 A1）：email/phone 另補 blind index 欄（migration 114），
# 供 login/去重等值查——S5 DROP 明文後唯一可查路徑。
USER_PII_BIDX_FIELDS: dict[str, str] = {
    "email": "email_bidx",
    "phone": "phone_bidx",
}


async def encrypt_user_pii(
    subject_user_id: str,
    tenant_id: str | None,
    fields: dict[str, str | None],
) -> dict[str, str | None]:
    """把 users 明文 PII 值轉密文欄＋盲索引欄值（dual-write 同句寫入用）。

    fields 的 key 必須 ∈ USER_PII_FIELDS；回傳只含傳入欄位的
    {"<欄>_enc": 密文|None}，email/phone 另帶 {"<欄>_bidx": 索引|None}。
    值 None/空白 → None（與明文語意一致）。
    """
    from core import user_pii_bidx

    out: dict[str, str | None] = {}
    for key, value in fields.items():
        out[USER_PII_FIELDS[key]] = await encrypt_pii(subject_user_id, tenant_id, value)
        if key in USER_PII_BIDX_FIELDS:
            out[USER_PII_BIDX_FIELDS[key]] = user_pii_bidx.blind_index(value)
    return out


async def dual_write_user_pii(
    subject_user_id: str,
    tenant_id: str | None,
    fields: dict[str, str | None],
) -> None:
    """INSERT 後補寫品牌庫 users 的 *_enc 欄（id 由 RETURNING 才確定的場合）。

    設計上 enc 只會「缺」不會「舊」：與明文同交易時原子；交易外中斷時 enc 留
    NULL → dual-read 回退明文、S3 backfill 兜底。UPDATE 場合請改用
    encrypt_user_pii 併入同一句 UPDATE（避免明文已變、enc 補寫失敗的 stale）。
    """
    if not fields:
        return
    enc = await encrypt_user_pii(subject_user_id, tenant_id, fields)
    sets = ", ".join(f"{col} = %s" for col in enc)
    await db_module._conn.execute(
        f"UPDATE users SET {sets} WHERE id = %s::uuid",
        (*enc.values(), subject_user_id),
    )


async def decrypt_user_pii_row(subject_user_id: str, row: dict) -> dict:
    """dual-read：enc 優先、明文回退（CIA §9 S2）。回新 dict，*_enc 欄一律剝除。

    - enc 有值 → 解密為明文；DEK 已銷毀（crypto-shred）→ **None，不回退明文**
      （fail-closed：銷毀即不可讀；正常 forget 流程明文同步已清，此為防禦深度）。
    - enc 無值（backfill 前/舊列）→ 保留明文欄現值（過渡窗明文仍權威）。
    """
    out = dict(row)
    for plain_col, enc_col in USER_PII_FIELDS.items():
        if enc_col not in row:
            continue
        cipher = out.pop(enc_col)
        if cipher:
            out[plain_col] = await decrypt_pii(subject_user_id, cipher)
    return out
