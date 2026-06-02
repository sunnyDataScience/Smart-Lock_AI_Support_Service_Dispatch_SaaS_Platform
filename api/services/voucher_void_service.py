"""Voucher Void 業務邏輯 — 紅字沖銷（append-only）。

設計決策（ADR-VCH-001/002 / CR-0004 §8 HD-VCH-001~004）：
  - HD-VCH-002 append-only：原傳票永不 UPDATE；沖銷 = 新建反向分錄 + voucher_void_event
  - 紅字：debit/credit 對調（借貸互換表達沖銷語意）；amount 同額正數
  - hash chain V1：hash_self = sha256(voucher_no|amount|debit|credit|reverses_voucher_id|hash_prev)
  - 410：目標傳票本身是反向分錄（reverses_voucher_id IS NOT NULL）→ 不可再沖
  - 409：voucher_void_event 已存在（UNIQUE voucher_id）→ 已被沖銷過
  - 404：saas.voucher 不存在
  - 原子性：整個沖銷在一個 transaction 內完成（transaction + 兩次 INSERT）
"""

from __future__ import annotations

import hashlib
import logging
import uuid as uuid_module

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.voucher_void_service")

_VALID_REASON = {"error_correction", "customer_dispute", "tax_adjust"}

# SELECT 欄位（對應 saas.voucher 全欄）
_VOUCHER_SELECT = (
    "id, tenant_id, voucher_no, period, related_entity_type, related_entity_id, "
    "debit_account, credit_account, amount, currency, posting_date, memo, "
    "reason_code, reverses_voucher_id, issuer_party, legal_basis, "
    "hash_prev, hash_self, created_at"
)

# 欄位順序對齊 _VOUCHER_SELECT（19 欄）：
# [0]=id, [1]=tenant_id, [2]=voucher_no, [3]=period, [4]=related_entity_type,
# [5]=related_entity_id, [6]=debit_account, [7]=credit_account, [8]=amount,
# [9]=currency, [10]=posting_date, [11]=memo, [12]=reason_code,
# [13]=reverses_voucher_id, [14]=issuer_party, [15]=legal_basis,
# [16]=hash_prev, [17]=hash_self, [18]=created_at


def _row_to_voucher_dict(row: tuple) -> dict:
    """saas.voucher row → dict（對齊 spec Voucher schema 關鍵欄）。"""
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "voucher_no": row[2],
        "period": row[3],
        "related_entity_type": row[4],
        "related_entity_id": str(row[5]) if row[5] else None,
        "debit_account": row[6],
        "credit_account": row[7],
        "amount": f"{float(row[8]):.2f}",
        "currency": row[9] or "TWD",
        "posting_date": row[10].isoformat() if row[10] else None,
        "memo": row[11],
        "reason_code": row[12],
        "reverses_voucher_id": str(row[13]) if row[13] else None,
        "issuer_party": row[14],
        "legal_basis": row[15],
        "hash_prev": row[16],
        "hash_self": row[17],
        "created_at": row[18].isoformat() if row[18] else None,
    }


def _compute_hash_self(
    voucher_no: str,
    amount: str,
    debit_account: str | None,
    credit_account: str | None,
    reverses_voucher_id: str | None,
    hash_prev: str | None,
) -> str:
    """計算 hash_self（HD-VCH-001 hash chain V1）。

    格式：sha256(voucher_no|amount|debit|credit|reverses_voucher_id|hash_prev)
    各欄位若為 None 則用空字串。
    """
    parts = "|".join(
        [
            voucher_no or "",
            amount or "",
            debit_account or "",
            credit_account or "",
            reverses_voucher_id or "",
            hash_prev or "",
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


async def void_voucher(
    *,
    voucher_id: str,
    reason: str,
    comment: str | None,
    keeper_user_id: str,
) -> dict:
    """紅字沖銷傳票。

    Returns:
        reversal voucher dict（新建的反向分錄）

    Raises:
        ApiError 404 NOT_FOUND: 原傳票不存在
        ApiError 410 ALREADY_REVERSED: 目標本身已是反向分錄
        ApiError 409 ALREADY_VOIDED: 此傳票已被沖銷過
        ApiError 503 DB_UNAVAILABLE: DB 不可用
        ApiError 422 VALIDATION_ERROR: reason 非法值
    """
    if reason not in _VALID_REASON:
        raise ApiError(
            "VALIDATION_ERROR",
            f"reason must be one of: {', '.join(sorted(_VALID_REASON))}",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    async with db_module._conn.transaction():
        # ── Step 1: SELECT 原 voucher
        cur = await db_module._conn.execute(
            f"SELECT {_VOUCHER_SELECT} FROM saas.voucher WHERE id = %s::uuid",
            [voucher_id],
        )
        original_row = await cur.fetchone()
        if not original_row:
            raise ApiError("NOT_FOUND", "Voucher not found", 404)

        original = _row_to_voucher_dict(original_row)

        # ── Step 2: 410 — 原 voucher 本身是反向分錄（HD-VCH-002）
        if original["reverses_voucher_id"] is not None:
            raise ApiError(
                "ALREADY_REVERSED",
                "Target voucher is itself a reversal entry and cannot be voided again",
                410,
            )

        # ── Step 3: 409 — 已被沖銷過（voucher_void_event UNIQUE voucher_id）
        chk = await db_module._conn.execute(
            "SELECT id FROM saas.voucher_void_event WHERE voucher_id = %s::uuid",
            [voucher_id],
        )
        existing_event = await chk.fetchone()
        if existing_event:
            raise ApiError(
                "ALREADY_VOIDED",
                "Voucher has already been voided",
                409,
            )

        # ── Step 4: 建反向分錄 voucher（紅字：debit/credit 對調）
        reversal_id = str(uuid_module.uuid4())
        reversal_voucher_no = original["voucher_no"] + "-R"

        # hash chain：hash_prev = 原 voucher.hash_self
        hash_prev = original["hash_self"]
        amount_str = original["amount"]  # 已是 "xx.xx" 格式
        reversal_debit = original["credit_account"]   # 借貸對調
        reversal_credit = original["debit_account"]   # 借貸對調
        hash_self = _compute_hash_self(
            voucher_no=reversal_voucher_no,
            amount=amount_str,
            debit_account=reversal_debit,
            credit_account=reversal_credit,
            reverses_voucher_id=voucher_id,
            hash_prev=hash_prev,
        )

        await db_module._conn.execute(
            """
            INSERT INTO saas.voucher (
                id, tenant_id, voucher_no, period,
                related_entity_type, related_entity_id,
                debit_account, credit_account, amount, currency,
                posting_date, memo, reason_code,
                reverses_voucher_id,
                issuer_party, legal_basis,
                hash_prev, hash_self
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s::uuid,
                %s, %s,
                %s, %s
            )
            """,
            [
                reversal_id,
                original["tenant_id"],
                reversal_voucher_no,
                original["period"],
                original["related_entity_type"],
                original["related_entity_id"],
                reversal_debit,
                reversal_credit,
                original_row[8],  # 原始 numeric，避免 float 精度問題
                original["currency"],
                original_row[10],  # posting_date 原始 date 物件
                original["memo"],
                reason,
                voucher_id,
                original["issuer_party"] or "platform",
                original["legal_basis"],
                hash_prev,
                hash_self,
            ],
        )

        # ── Step 5: INSERT voucher_void_event
        await db_module._conn.execute(
            """
            INSERT INTO saas.voucher_void_event (
                tenant_id, voucher_id, reversal_voucher_id,
                reason, comment, keeper_user_id
            ) VALUES (
                %s::uuid, %s::uuid, %s::uuid,
                %s, %s, %s::uuid
            )
            """,
            [
                original["tenant_id"],
                voucher_id,
                reversal_id,
                reason,
                comment,
                keeper_user_id,
            ],
        )

        logger.info(
            "Voucher voided: original=%s reversal=%s reason=%s keeper=%s",
            voucher_id,
            reversal_id,
            reason,
            keeper_user_id,
        )

        # ── Step 6: 回傳新建的反向分錄
        cur2 = await db_module._conn.execute(
            f"SELECT {_VOUCHER_SELECT} FROM saas.voucher WHERE id = %s::uuid",
            [reversal_id],
        )
        reversal_row = await cur2.fetchone()
        return _row_to_voucher_dict(reversal_row)
