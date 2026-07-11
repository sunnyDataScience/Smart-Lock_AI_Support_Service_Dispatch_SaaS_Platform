"""GDPR Forget Service — FR-0053 Phase II MVP。

兩階段刪除流程：
  T0: received → 檢查 legal-hold → soft_deleted (clear PII + 標記)
                                  → legal_hold_denied (拒絕，7d 內通知)
  T+30: soft_deleted → hard_deleted (physical delete users row)

對齊 ADR-PII-002 雙層防線：
  T0 soft_delete = clear PII fields (display_name, email, phone) + status flag
  T+30 hard_delete = DELETE row + audit ledger preserved (≥7 yr retention)

cron hard-delete worker 留下輪；本 commit 提供 service ops 供 admin manual
觸發 + future cron 接入。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.tech_mirror import mirror_rows
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service

logger = logging.getLogger("api.gdpr_forget_service")

# GDPR cooldown 30 天硬刪 (BR-PII-001)
HARD_DELETE_COOLDOWN_DAYS = 30


async def _forget_audit(
    *, action: str, tenant_id: str, subject_user_id: str,
    actor_user_id: str | None, request_id: str, extra: dict | None = None,
) -> None:
    """CR-0164 D：GDPR forget 全流程 append-only audit（原全程零稽核，違 FR-API-16/
    NFR-Priv-005）。audit_events 無 tenant_id 欄 → tenant_id 入 payload。target_id
    取 subject（actor_id FK ON DELETE SET NULL、target_id 無 FK，subject 被刪後稽核仍存活）。
    best-effort（log_event 內部吞錯不 raise），但**不再靜默掩蓋業務失敗**。
    """
    payload = {"tenant_id": tenant_id, "subject_user_id": subject_user_id,
               "forget_request_id": request_id}
    if extra:
        payload.update(extra)
    await audit_log_service.log_event(
        event_type="compliance", actor_id=actor_user_id, actor_role="admin",
        action=action, target_type="user", target_id=subject_user_id, payload=payload)


async def _has_active_legal_hold(subject_user_id: str) -> bool:
    """CR-0164 D2：subject 名下有 legal_hold=true 且未刪的 media → forget 須擋（423）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM media_files "
        "WHERE uploader_user_id = %s::uuid AND legal_hold = TRUE AND deleted_at IS NULL "
        "LIMIT 1",
        (subject_user_id,))
    return (await cur.fetchone()) is not None


async def create_forget_request(
    *,
    tenant_id: str,
    subject_user_id: str,
    requested_by: str = "customer_self",
    actor_user_id: str | None = None,
    notes: str | None = None,
) -> dict:
    """T0：建 forget request（status='received'）。

    legal-hold check 在後續 process_request 跑（避免初始建立耗時）。
    requested_by ∈ {customer_self, admin, dpo}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if requested_by not in ("customer_self", "admin", "dpo"):
        raise ApiError(
            "VALIDATION_ERROR", f"invalid requested_by: {requested_by}", 422,
        )

    # 取 subject 的 email 用於 audit (hard delete 後保留參考)
    cur = await db_module._conn.execute(
        "SELECT email FROM users WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (subject_user_id, tenant_id),
    )
    user_row = await cur.fetchone()
    if not user_row:
        raise ApiError("NOT_FOUND", "subject user not found in tenant", 404)
    subject_email = user_row[0]

    # 冪等：同 user 已有 pending request (received/soft_deleted) → 回 existing
    cur = await db_module._conn.execute(
        "SELECT id, status, received_at FROM saas.forget_request "
        "WHERE subject_user_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND status IN ('received', 'soft_deleted') "
        "ORDER BY received_at DESC LIMIT 1",
        (subject_user_id, tenant_id),
    )
    existing = await cur.fetchone()
    if existing:
        logger.info(
            "forget_request idempotent hit: user=%s existing=%s status=%s",
            subject_user_id[:8], str(existing[0])[:8], existing[1],
        )
        return await _get_request(str(existing[0]))

    cur = await db_module._conn.execute(
        "INSERT INTO saas.forget_request "
        "  (tenant_id, subject_user_id, subject_email, requested_by, "
        "   actor_user_id, notes) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, %s) "
        "RETURNING id",
        (tenant_id, subject_user_id, subject_email, requested_by,
         actor_user_id, notes),
    )
    row = await cur.fetchone()
    request_id = str(row[0])
    logger.info(
        "forget_request created: user=%s id=%s by=%s",
        subject_user_id[:8], request_id[:8], requested_by,
    )
    await _forget_audit(
        action="gdpr_forget_received", tenant_id=tenant_id,
        subject_user_id=subject_user_id, actor_user_id=actor_user_id,
        request_id=request_id, extra={"requested_by": requested_by})
    return await _get_request(request_id)


async def _get_request(request_id: str) -> dict:
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, subject_user_id, subject_email, status, "
        "       requested_by, legal_hold_reason, expected_release_at, "
        "       received_at, soft_deleted_at, hard_delete_eligible_at, "
        "       hard_deleted_at, actor_user_id, notes "
        "FROM saas.forget_request WHERE id = %s::uuid",
        (request_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "forget_request not found", 404)
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "subject_user_id": str(row[2]),
        "subject_email": row[3],
        "status": row[4],
        "requested_by": row[5],
        "legal_hold_reason": row[6],
        "expected_release_at": row[7].isoformat() if row[7] else None,
        "received_at": row[8].isoformat() if row[8] else None,
        "soft_deleted_at": row[9].isoformat() if row[9] else None,
        "hard_delete_eligible_at": row[10].isoformat() if row[10] else None,
        "hard_deleted_at": row[11].isoformat() if row[11] else None,
        "actor_user_id": str(row[12]) if row[12] else None,
        "notes": row[13],
    }


async def deny_legal_hold(
    *,
    request_id: str,
    legal_hold_reason: str,
    expected_release_at: datetime | None = None,
    actor_user_id: str | None = None,
) -> dict:
    """admin/DPO 標記 legal-hold 拒絕（received → legal_hold_denied）。

    7 天內通知客戶（業務 SOP 流程，本 service 只標 status）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if not legal_hold_reason or len(legal_hold_reason.strip()) < 5:
        raise ApiError("VALIDATION_ERROR", "legal_hold_reason ≥5 字元", 422)

    upd = await db_module._conn.execute(
        "UPDATE saas.forget_request SET "
        "  status = 'legal_hold_denied', "
        "  legal_hold_reason = %s, "
        "  expected_release_at = %s, "
        "  actor_user_id = COALESCE(%s::uuid, actor_user_id), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'received' "
        "RETURNING id",
        (
            legal_hold_reason.strip()[:1000],
            expected_release_at.isoformat() if expected_release_at else None,
            actor_user_id, request_id,
        ),
    )
    if not await upd.fetchone():
        raise ApiError(
            "STATE_CONFLICT",
            "request not in 'received' state for legal_hold_denied",
            409,
        )
    _r = await _get_request(request_id)
    await _forget_audit(
        action="gdpr_forget_legal_hold_denied", tenant_id=_r["tenant_id"],
        subject_user_id=_r["subject_user_id"], actor_user_id=actor_user_id,
        request_id=request_id, extra={"legal_hold_reason": legal_hold_reason.strip()[:200]})
    return _r


async def soft_delete(
    *, request_id: str, actor_user_id: str | None = None,
) -> dict:
    """T0+：received → soft_deleted。

    clear PII：display_name='[REDACTED]', email='[REDACTED]', phone=NULL。
    寫 hard_delete_eligible_at = NOW + 30 days。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    req = await _get_request(request_id)
    if req["status"] != "received":
        raise ApiError(
            "STATE_CONFLICT",
            f"request status='{req['status']}'，不可 soft_delete",
            409,
        )

    subject_user_id = req["subject_user_id"]

    # CR-0164 D2：legal-hold 前置擋——subject 名下有 legal_hold media → 423 拒絕
    # （TC-COMPLIANCE-02 P0；不再靠 admin 手動先 deny 的順序相依）。
    if await _has_active_legal_hold(subject_user_id):
        await _forget_audit(
            action="gdpr_forget_blocked", tenant_id=req["tenant_id"],
            subject_user_id=subject_user_id, actor_user_id=actor_user_id,
            request_id=request_id, extra={"reason": "legal_hold_active"})
        raise ApiError(
            "LEGAL_HOLD_ACTIVE",
            "subject 名下有 legal-hold 中的證據，forget 暫不可執行（須先解除 legal-hold）",
            423,
        )

    eligible_at = datetime.now(timezone.utc) + timedelta(
        days=HARD_DELETE_COOLDOWN_DAYS,
    )

    # 1. clear PII on users(CR-0112:技師列須改權威庫 + 鏡射,否則權威庫留 PII)
    # CR-0164 D：PII 清除失敗屬硬失敗——不再靜默吞例外後仍標 soft_deleted（假性合規）。
    _is_tech = False
    if db_module.tech_db_enabled():  # fallback 模式免探查(不擾動單庫行為/測試)
        rcur = await db_module._conn.execute(
            "SELECT role FROM users WHERE id = %s::uuid", (subject_user_id,))
        rrow = await rcur.fetchone()
        _is_tech = bool(rrow) and rrow[0] == "technician"
    _conn = await db_module.require_tech_conn() if _is_tech else db_module._conn
    await _conn.execute(
        "UPDATE users SET "
        "  display_name = '[REDACTED]', "
        "  email = '[REDACTED-' || id::text || ']', "
        "  phone = NULL, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (subject_user_id,),
    )
    if _is_tech:
        await mirror_rows("users", [subject_user_id])

    # 2. UPDATE forget_request status
    upd = await db_module._conn.execute(
        "UPDATE saas.forget_request SET "
        "  status = 'soft_deleted', "
        "  soft_deleted_at = NOW(), "
        "  hard_delete_eligible_at = %s, "
        "  actor_user_id = COALESCE(%s::uuid, actor_user_id), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'received' "
        "RETURNING id",
        (eligible_at.isoformat(), actor_user_id, request_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    await _forget_audit(
        action="gdpr_forget_soft_deleted", tenant_id=req["tenant_id"],
        subject_user_id=subject_user_id, actor_user_id=actor_user_id,
        request_id=request_id, extra={"hard_delete_eligible_at": eligible_at.isoformat()})
    return await _get_request(request_id)


async def hard_delete(
    *, request_id: str, actor_user_id: str | None = None,
) -> dict:
    """T+30：soft_deleted → hard_deleted (physical delete users row)。

    驗 hard_delete_eligible_at <= NOW（強制 30 天 cooldown）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    req = await _get_request(request_id)
    if req["status"] != "soft_deleted":
        raise ApiError(
            "STATE_CONFLICT",
            f"request status='{req['status']}'，必須 soft_deleted 才能 hard_delete",
            409,
        )

    eligible_at_str = req.get("hard_delete_eligible_at")
    if not eligible_at_str:
        raise ApiError(
            "STATE_CONFLICT",
            "hard_delete_eligible_at missing",
            409,
        )
    eligible_at = datetime.fromisoformat(eligible_at_str.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) < eligible_at:
        raise ApiError(
            "STATE_CONFLICT",
            f"cooldown 未滿（eligible_at={eligible_at_str}）",
            409,
        )

    subject_user_id = req["subject_user_id"]

    # 1. 嘗試實體 DELETE users row。CR-0164 D1（方案 A）：soft_delete 已把 PII 匿名化
    # （GDPR Art.17 承認匿名化等同抹除）；若 FK（complaints/disputes/refund_requests/
    # warranty_claims/… NO ACTION）阻擋實體刪除，**匿名化即終態**，不再靜默吞例外後
    # 假性標記成功——改如實記錄 physical_deleted 真值於 audit。非 FK 的例外照拋（不掩蓋）。
    physical_deleted = False
    try:
        _is_tech = False
        if db_module.tech_db_enabled():
            rcur = await db_module._conn.execute(
                "SELECT role FROM users WHERE id = %s::uuid", (subject_user_id,))
            rrow = await rcur.fetchone()
            _is_tech = bool(rrow) and rrow[0] == "technician"
        _conn = await db_module.require_tech_conn() if _is_tech else db_module._conn
        del_cur = await _conn.execute(
            "DELETE FROM users WHERE id = %s::uuid", (subject_user_id,))
        physical_deleted = (del_cur.rowcount or 0) > 0
        if _is_tech:
            await mirror_rows("users", [subject_user_id])
    except Exception as exc:  # noqa: BLE001
        # FK 阻擋 → 匿名化保留終態（方案 A）；其他 DB 錯誤照拋，不掩蓋
        msg = str(exc).lower()
        if "foreign key" in msg or "violates" in msg or "referenced" in msg:
            await db_module._conn.execute("ROLLBACK")
            physical_deleted = False
            logger.info(
                "hard_delete FK-blocked → anonymized-retained (方案A) user=%s",
                subject_user_id[:8])
        else:
            raise

    # 2. UPDATE forget_request → hard_deleted（匿名化即終態，physical 真值記 audit）
    upd = await db_module._conn.execute(
        "UPDATE saas.forget_request SET "
        "  status = 'hard_deleted', "
        "  hard_deleted_at = NOW(), "
        "  actor_user_id = COALESCE(%s::uuid, actor_user_id), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'soft_deleted' "
        "RETURNING id",
        (actor_user_id, request_id),
    )
    if not await upd.fetchone():
        raise ApiError("STATE_CONFLICT", "concurrent state change", 409)
    await _forget_audit(
        action="gdpr_forget_hard_deleted", tenant_id=req["tenant_id"],
        subject_user_id=subject_user_id, actor_user_id=actor_user_id,
        request_id=request_id,
        extra={"physical_deleted": physical_deleted,
               "disposition": "physical_delete" if physical_deleted else "anonymized_retained_fk"})
    return await _get_request(request_id)


async def cancel_request(
    *, request_id: str, actor_user_id: str | None = None,
) -> dict:
    """客戶撤回 forget request（received → cancelled）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    upd = await db_module._conn.execute(
        "UPDATE saas.forget_request SET "
        "  status = 'cancelled', "
        "  actor_user_id = COALESCE(%s::uuid, actor_user_id), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'received' "
        "RETURNING id",
        (actor_user_id, request_id),
    )
    if not await upd.fetchone():
        raise ApiError(
            "STATE_CONFLICT", "only 'received' state can be cancelled", 409,
        )
    _r = await _get_request(request_id)
    await _forget_audit(
        action="gdpr_forget_cancelled", tenant_id=_r["tenant_id"],
        subject_user_id=_r["subject_user_id"], actor_user_id=actor_user_id,
        request_id=request_id)
    return _r


async def list_forget_requests(
    *, tenant_id: str, status: str | None = None, limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 200:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..200", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if status:
        where.append("status = %s")
        args.append(status)
    args.append(limit)

    cur = await db_module._conn.execute(
        "SELECT id FROM saas.forget_request "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY received_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = []
    for r in rows:
        try:
            items.append(await _get_request(str(r[0])))
        except ApiError:
            continue
    return {"items": items, "total": len(items)}
