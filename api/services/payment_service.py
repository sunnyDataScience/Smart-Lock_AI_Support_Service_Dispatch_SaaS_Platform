"""金流 payment service（CR-0070 / TI-FIN-PAY-01~05；mock-first 骨架）。

會議決議 5 授權 mock-first：本服務落地三軌支付的 intent/confirm/webhook 冪等/
fallback audit/現金爭議與 payment gate 語意，所有 payment 標 is_mock；正式 provider
（真 Line Pay / Apple Pay 簽章金鑰串接）由 Sunny 下輪（決議 6）替換，DB schema 不變。

對應：
  PAY-01 assert_payment_gate     —— config 開時，建 WO/派工前須有 confirmed 付款或訂金
  PAY-02 create_payment_intent   —— 三軌 cash / apple_pay / line_pay → pending intent
  PAY-03 handle_linepay_webhook  —— 簽章驗證 + provider_txn_id 冪等（重複 webhook 不重複認）
  PAY-04 record_payment_fallback —— Line Pay 失敗 → cash 兩次嘗試 audit
  PAY-05 report_cash_dispute     —— 現金金額不符 → disputes 表（≥ 門檻 flag + payment disputed）
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.payment_service")

_VALID_METHODS = {"cash", "apple_pay", "line_pay"}
_VALID_PURPOSES = {"service", "deposit"}
# mock 簽章金鑰（正式環境由 Secret Manager 注入 LINE_PAY_CHANNEL_SECRET 取代）
_MOCK_LINEPAY_SECRET = "mock-linepay-secret"
# 現金爭議告警門檻（金額差 ≥ 此值即 flag）；正式可移入 M18 config
_CASH_DISPUTE_THRESHOLD_DEFAULT = 500.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sign_linepay_payload(payload: str, secret: str = _MOCK_LINEPAY_SECRET) -> str:
    """mock Line Pay 簽章：HMAC-SHA256(secret, payload)。正式版同演算法換真金鑰。"""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _verify_linepay_signature(payload: str, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign_linepay_payload(payload, secret), signature or "")


async def create_payment_intent(
    *,
    tenant_id: str,
    work_order_id: str | None,
    method: str,
    amount: float,
    purpose: str = "service",
    idempotency_key: str | None = None,
) -> dict:
    """建立支付 intent（pending）。同 (tenant, idempotency_key) 重送 → 回既有（冪等）。"""
    if method not in _VALID_METHODS:
        raise ApiError("VALIDATION_ERROR", f"method must be one of {sorted(_VALID_METHODS)}", 422)
    if purpose not in _VALID_PURPOSES:
        raise ApiError("VALIDATION_ERROR", f"purpose must be one of {sorted(_VALID_PURPOSES)}", 422)
    if amount is None or float(amount) < 0:
        raise ApiError("VALIDATION_ERROR", "amount must be >= 0", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 冪等：同 key 已有 → 回既有
    if idempotency_key:
        cur = await db_module._conn.execute(
            "SELECT id, intent_id, status, method, amount FROM payments "
            "WHERE tenant_id = %s::uuid AND idempotency_key = %s",
            (tenant_id, idempotency_key))
        ex = await cur.fetchone()
        if ex:
            return {"id": str(ex[0]), "intent_id": ex[1], "status": ex[2], "method": ex[3],
                    "amount": float(ex[4]), "deduplicated": True}

    intent_id = f"intent_{uuid.uuid4().hex[:20]}"
    cur = await db_module._conn.execute(
        "INSERT INTO payments (tenant_id, work_order_id, method, amount, purpose, "
        "  status, intent_id, idempotency_key) "
        "VALUES (%s::uuid, %s, %s, %s, %s, 'pending', %s, %s) "
        "RETURNING id",
        (tenant_id, work_order_id, method, amount, purpose, intent_id, idempotency_key))
    row = await cur.fetchone()
    return {"id": str(row[0]), "intent_id": intent_id, "status": "pending",
            "method": method, "amount": float(amount), "deduplicated": False}


async def confirm_payment(
    *, tenant_id: str, intent_id: str, provider_txn_id: str | None = None,
) -> dict:
    """pending → confirmed（設 confirmed_at + provider_txn_id）。已 confirmed 重呼 → 回既有（冪等）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, status FROM payments WHERE tenant_id = %s::uuid AND intent_id = %s",
        (tenant_id, intent_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "payment intent not found", 404)
    pid, status = str(row[0]), row[1]
    if status == "confirmed":
        return {"id": pid, "intent_id": intent_id, "status": "confirmed", "deduplicated": True}
    if status not in ("pending",):
        raise ApiError("STATE_CONFLICT", f"cannot confirm payment in status '{status}'", 409)
    await db_module._conn.execute(
        "UPDATE payments SET status='confirmed', confirmed_at=NOW(), "
        "  provider_txn_id=COALESCE(%s, provider_txn_id), updated_at=NOW() "
        "WHERE id=%s::uuid", (provider_txn_id, pid))
    return {"id": pid, "intent_id": intent_id, "status": "confirmed", "deduplicated": False}


async def handle_linepay_webhook(
    *, payload: str, signature: str, provider_txn_id: str, intent_id: str,
    tenant_id: str, secret: str = _MOCK_LINEPAY_SECRET,
) -> dict:
    """PAY-03：Line Pay webhook —— 驗簽 + provider_txn_id 冪等（重複 webhook 不重複認款）。"""
    if not _verify_linepay_signature(payload, signature, secret):
        raise ApiError("SIGNATURE_INVALID", "Line Pay webhook signature invalid", 401)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 冪等：同 provider_txn_id 已認過 → 直接回既有（不重複 confirm）
    cur = await db_module._conn.execute(
        "SELECT id, status FROM payments WHERE provider_txn_id = %s", (provider_txn_id,))
    ex = await cur.fetchone()
    if ex:
        return {"id": str(ex[0]), "status": ex[1], "duplicate_webhook": True}
    out = await confirm_payment(tenant_id=tenant_id, intent_id=intent_id,
                                provider_txn_id=provider_txn_id)
    out["duplicate_webhook"] = False
    return out


async def record_payment_fallback(
    *, tenant_id: str, failed_intent_id: str, new_method: str, amount: float,
    work_order_id: str | None = None,
) -> dict:
    """PAY-04：支付 fallback 兩次嘗試 audit —— 原 intent 標 failed，新 method 建 intent
    記 fallback_from + attempt_count=2，供稽核兩軌嘗試軌跡。"""
    if new_method not in _VALID_METHODS:
        raise ApiError("VALIDATION_ERROR", f"method must be one of {sorted(_VALID_METHODS)}", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, method FROM payments WHERE tenant_id=%s::uuid AND intent_id=%s",
        (tenant_id, failed_intent_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "failed payment intent not found", 404)
    failed_method = row[1]
    await db_module._conn.execute(
        "UPDATE payments SET status='failed', updated_at=NOW() WHERE id=%s::uuid", (str(row[0]),))
    new_intent = f"intent_{uuid.uuid4().hex[:20]}"
    cur = await db_module._conn.execute(
        "INSERT INTO payments (tenant_id, work_order_id, method, amount, status, intent_id, "
        "  attempt_count, fallback_from) "
        "VALUES (%s::uuid, %s, %s, %s, 'pending', %s, 2, %s) RETURNING id",
        (tenant_id, work_order_id, new_method, amount, new_intent, failed_method))
    nid = str((await cur.fetchone())[0])
    return {"id": nid, "intent_id": new_intent, "status": "pending", "method": new_method,
            "attempt_count": 2, "fallback_from": failed_method}


async def report_cash_dispute(
    *, tenant_id: str, payment_id: str, filed_by: str, reported_amount: float,
    reason: str, threshold: float = _CASH_DISPUTE_THRESHOLD_DEFAULT,
) -> dict:
    """PAY-05：現金金額不符 → disputes 表。差額 ≥ 門檻 → flag + payment 標 disputed。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT amount, work_order_id, method FROM payments "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid", (payment_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "payment not found", 404)
    expected = float(row[0]); wo_id = row[1]
    delta = abs(expected - float(reported_amount))
    flagged = delta >= threshold
    dcur = await db_module._conn.execute(
        "INSERT INTO disputes (work_order_id, filed_by, dispute_type, status, description, "
        "  evidence, sla_deadline) "
        "VALUES (%s, %s::uuid, 'cash_amount_mismatch', 'open', %s, %s::jsonb, NOW()+INTERVAL '24 hours') "
        "RETURNING id",
        (wo_id, filed_by, reason,
         f'{{"expected": {expected}, "reported": {reported_amount}, "delta": {delta}}}'))
    did = str((await dcur.fetchone())[0])
    if flagged:
        await db_module._conn.execute(
            "UPDATE payments SET status='disputed', updated_at=NOW() WHERE id=%s::uuid", (payment_id,))
    return {"dispute_id": did, "delta": round(delta, 2), "threshold": threshold,
            "flagged": flagged}


async def assert_payment_gate(*, tenant_id: str, work_order_id: str) -> dict:
    """PAY-01：派工/建 WO 前 payment gate。config payment_gate.require_payment_for_dispatch
    開啟時，須有該 WO 的 confirmed 付款或訂金（deposit），否則 422。預設 config 缺 → 不擋。"""
    from services import config_m18_service
    cfg = await config_m18_service.read_global_value(namespace="payment_gate")
    require = bool(cfg.get("require_payment_for_dispatch")) if isinstance(cfg, dict) else False
    if not require:
        return {"gate": "disabled", "passed": True}
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT 1 FROM payments WHERE work_order_id=%s::uuid AND status='confirmed' "
        "  AND purpose IN ('service','deposit') LIMIT 1", (work_order_id,))
    if not await cur.fetchone():
        raise ApiError("PAYMENT_REQUIRED_FOR_DISPATCH",
                       "派工前須有付款證明或訂金（payment_gate.require_payment_for_dispatch）", 422)
    return {"gate": "enabled", "passed": True}
