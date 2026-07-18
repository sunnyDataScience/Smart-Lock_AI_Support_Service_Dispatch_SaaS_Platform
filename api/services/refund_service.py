"""Refund Requests 業務邏輯。

範圍：
- listRefundRequests（cursor + limit + status + work_order_id）
- getRefundRequest
- submitRefundDecision（pending → approved/rejected/escalated；append approval_chain）

OpenAPI RefundRequest schema：
    id, work_order_id, requested_by, amount (decimal str), reason, status (6 enum),
    created_at, updated_at; invoice_id?, complaint_id?, requires_dual_sign?,
    approval_chain (array of objects)?, executed_at?

DB ↔ API 對齊：
  - refund_requests.amount (FLOAT)        → decimal string with 2 decimals
  - refund_requests.status (varchar(50))  → API RefundRequestStatus，best-effort 直通：
        pending / approved / rejected / escalated / executed / cancelled
        非預期值 → 視為 pending（避免破壞 enum 約束）
  - approval_chain (jsonb)                → 直通；NULL → []
  - requires_dual_sign (bool)             → 直通；NULL → False

租戶隔離：refund_requests 沒 tenant_id，透過
    JOIN work_orders → problem_cards → conversations → users
延伸 4 層 JOIN 取 users.tenant_id 過濾（與 invoice_service 同 pattern）。

雙簽流程（已實作 v1.29.0+，2026-06-04 docstring 校正）：
  submit_decision() 完整支援 csm_approved 中介態：
    pending → approve（!requires_dual_sign）→ approved
    pending → approve（requires_dual_sign）→ csm_approved（等第二簽）
    csm_approved → approve（不同 user）→ approved
    pending|csm_approved → reject → rejected
    pending → escalate → escalated
  requires_dual_sign 預設由金額 >= _DUAL_SIGN_THRESHOLD 自動判定（caller 可 override）。
  同一 user 不可在 approval_chain 中出現第二次（DUAL_SIGN_SAME_USER 409）。
  approval_chain JSONB append 每次決策紀錄（user_id / decision / reason / decided_at / stage）。
  agent 自動退款走獨立 single-actor endpoint `:agent-initiate`（CR-0009 ADR-0106
  LangGraph 特例；refunds_v2.py:150+）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor
# 重用 P1-A SoD primitive（鐵律：不得自己重寫三維 SoD 邏輯）
from services.cancellation_service import check_sod  # noqa: F401  re-exported

logger = logging.getLogger("api.refund_service")


_VALID_API_STATUS = {
    "pending",
    "csm_approved",  # v1.29.0：雙簽中介態
    "approved",
    "rejected",
    "escalated",
    "executed",
    "cancelled",
}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _coerce_status(raw: str | None) -> str:
    if raw and raw in _VALID_API_STATUS:
        return raw
    return "pending"


def _coerce_chain(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "invoice_id": str(row[2]) if row[2] else None,
        "complaint_id": str(row[3]) if row[3] else None,
        "requested_by": str(row[4]) if row[4] else None,
        "amount": _coerce_decimal(row[5]),
        "reason": row[6] or "",
        "status": _coerce_status(row[7]),
        "requires_dual_sign": bool(row[8]) if row[8] is not None else False,
        "approval_chain": _coerce_chain(row[9]),
        "executed_at": row[10].isoformat() if row[10] else None,
        "created_at": row[11].isoformat() if row[11] else None,
        "updated_at": row[12].isoformat() if row[12] else None,
        "document_number": row[13] if len(row) > 13 else None,
    }


_SELECT = (
    "r.id, r.work_order_id, r.invoice_id, r.complaint_id, r.requested_by, "
    "r.amount, r.reason, r.status, r.requires_dual_sign, r.approval_chain, "
    "r.executed_at, r.created_at, r.updated_at, r.document_number"
)

# ADR-009 §8 D1：dual_sign threshold（金額 >= 此額度自動要求雙簽，可被 caller override）
_DUAL_SIGN_THRESHOLD = 100000.0  # NT$ 100,000（對齊 SQL/Schema.sql comment）

_TENANT_JOIN = (
    "FROM refund_requests r "
    "JOIN work_orders wo ON r.work_order_id = wo.id "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "LEFT JOIN conversations c ON pc.conversation_id = c.id "
    "LEFT JOIN users u ON c.user_id = u.id"
)


async def list_refund_requests(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_API_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("r.status = %s")
        args.append(status)

    if work_order_id:
        where.append("r.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(r.created_at, r.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY r.created_at DESC, r.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_dict(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor({"ts": last[11].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_refund_request(*, tenant_id: str, refund_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE r.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (refund_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Refund request {refund_id} not found", 404)
    return _row_to_dict(row)


async def create_refund_request(
    *,
    tenant_id: str,
    work_order_id: str,
    amount: str,
    reason: str,
    reason_code: str,
    requested_by_role: str,
    requested_by: str,
    requires_dual_sign: bool | None = None,
) -> tuple[dict, bool]:
    """F-014 RefundCreditMemo 建立（ADR-009 D pattern, dual-trigger）。

    Idempotency: business unique key (work_order_id, reason_code) — 同 WO 同
    原因若已有非 rejected/cancelled 申請，回 200 既存。

    Dual-sign auto-determination: requires_dual_sign 若為 None，依金額 >=
    `_DUAL_SIGN_THRESHOLD` (NT$100,000) 自動設定。

    Returns: (refund_dict, created_flag)
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 驗證 WO 存在 + tenant 隔離
    cur = await db_module._conn.execute(
        "SELECT u.tenant_id FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid",
        (work_order_id,),
    )
    wo_row = await cur.fetchone()
    if not wo_row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    if str(wo_row[0]) != tenant_id:
        raise ApiError("NOT_FOUND", "Work order not found", 404)  # 跨 tenant 偽裝 404

    # 2. Idempotency check: 同 WO 同 reason_code 已存在 active row?
    cur = await db_module._conn.execute(
        "SELECT id FROM refund_requests "
        "WHERE work_order_id = %s::uuid AND reason_code = %s "
        "  AND status NOT IN ('rejected', 'cancelled') "
        "ORDER BY created_at ASC LIMIT 1",
        (work_order_id, reason_code),
    )
    existing = await cur.fetchone()
    if existing:
        refund = await get_refund_request(
            tenant_id=tenant_id, refund_id=str(existing[0]),
        )
        return refund, False

    # 3. Auto-determine dual-sign（caller 未指定時依金額判斷）
    if requires_dual_sign is None:
        try:
            requires_dual_sign = float(amount) >= _DUAL_SIGN_THRESHOLD
        except (TypeError, ValueError):
            requires_dual_sign = False

    # 4. INSERT + 自動 doc number
    cur = await db_module._conn.execute(
        "INSERT INTO refund_requests "
        "  (work_order_id, requested_by, amount, reason, reason_code, "
        "   requested_by_role, status, requires_dual_sign, document_number) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, "
        "        'pending', %s, generate_doc_number('RM', 'doc_seq_rm')) "
        "RETURNING id",
        (
            work_order_id, requested_by, float(amount), reason, reason_code,
            requested_by_role, requires_dual_sign,
        ),
    )
    new_row = await cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert refund request", 500)
    new_refund_id = str(new_row[0])

    refund = await get_refund_request(tenant_id=tenant_id, refund_id=new_refund_id)
    return refund, True


# 決策可從哪些狀態觸發
# - pending：尚未審核
# - csm_approved：已第一階段核准（雙簽中），等候第二人
_DECISION_FROM = {"pending", "csm_approved"}
_FIRST_SIGN_STATUS = "csm_approved"  # 雙簽：第一簽後的狀態
_FINAL_APPROVED_STATUS = "approved"
_REJECTED_STATUS = "rejected"
_ESCALATED_STATUS = "escalated"


async def submit_decision(
    *,
    tenant_id: str,
    refund_id: str,
    decision: str,
    reason: str,
    decided_by_user_id: str,
) -> dict:
    """提交退款決策，含雙簽流程。

    狀態機：
      pending → approve（!requires_dual_sign）→ approved
      pending → approve（requires_dual_sign）→ csm_approved（等第二簽）
      csm_approved → approve（不同 user）→ approved
      pending|csm_approved → reject → rejected
      pending → escalate → escalated

    雙簽規則：
      - 同一 user 不可在 chain 中出現第二次
      - csm_approved 階段必須有第二位（不同 user）按 approve 才會 final
    """
    if decision not in {"approve", "reject", "escalate"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be one of approve, reject, escalate",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT r.id, r.status, r.approval_chain, r.requires_dual_sign "
        f"{_TENANT_JOIN} "
        f"WHERE r.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1",
        (refund_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Refund request {refund_id} not found", 404)
    current = row[1]
    requires_dual_sign = bool(row[3]) if row[3] is not None else False
    if current not in _DECISION_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot decide refund in status '{current}'; expected one of {sorted(_DECISION_FROM)}",
            409,
        )

    chain = _coerce_chain(row[2])

    # 同一 user 不可重複簽
    prior_signers = {entry.get("user_id") for entry in chain if isinstance(entry, dict)}
    if decided_by_user_id in prior_signers:
        raise ApiError(
            "DUAL_SIGN_SAME_USER",
            "Same user cannot sign twice on the same refund",
            409,
        )

    # escalate 只允許 pending 階段（已雙簽中要 escalate 應走另一路徑）
    if decision == "escalate" and current != "pending":
        raise ApiError(
            "STATE_CONFLICT",
            "escalate is only allowed at 'pending' stage",
            409,
        )

    # 計算新狀態
    if decision == "reject":
        new_status = _REJECTED_STATUS
    elif decision == "escalate":
        new_status = _ESCALATED_STATUS
    else:  # approve
        if current == "csm_approved":
            # 第二簽完成 → final approved
            new_status = _FINAL_APPROVED_STATUS
        elif requires_dual_sign:
            # 第一簽完成 → 等第二簽
            new_status = _FIRST_SIGN_STATUS
        else:
            # 不需雙簽，直接 final
            new_status = _FINAL_APPROVED_STATUS

    chain.append(
        {
            "user_id": decided_by_user_id,
            "decision": decision,
            "reason": reason.strip()[:500],
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "stage": "first_sign"
            if new_status == _FIRST_SIGN_STATUS
            else "final",
        },
    )

    await db_module._conn.execute(
        "UPDATE refund_requests "
        "SET status = %s, approval_chain = %s::jsonb, updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_status, json.dumps(chain), refund_id),
    )
    result = await get_refund_request(tenant_id=tenant_id, refund_id=refund_id)

    # 即時推送（best-effort）
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            "/realtime/refunds",
            {
                "type": "refund.decision.made",
                "payload": {
                    "refund_id": refund_id,
                    "decision": decision,
                    "status": new_status,
                    "decided_by_user_id": decided_by_user_id,
                    "requires_dual_sign": requires_dual_sign,
                    "awaiting_second_sign": new_status == _FIRST_SIGN_STATUS,
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish refund.decision failed (non-fatal)")

    return result


# ═════════════════════════════════════════════════════════════════════════════
# P1-B — Refund 三維 SoD + 5-tier（ADR-0040 v2 / BR-REFUND-006 / FR-0014）
# ─────────────────────────────────────────────────────────────────────────────
# spec-alignment 垂直切片。把退款從「金額>10萬雙簽」升級為：
#   1. 5-tier 金額分級（伺服器端從 amount 推算，門檻 1k/5k/30k/100k，ADR-0040 §97-104）
#   2. refund_class 必填 enum（product/labor/material/travel/inspection）
#   3. 三維 SoD（initiator ≠ approver ≠ executor）— 重用 P1-A check_sod
#   4. amount > 0
#   5. terminal state 防護（rejected/executed 後不可再 approve）— BR-REFUND-003
#
# 對應 spec DB 形狀：docs/architecture/data/ddl-migration-001-init.sql saas.refund。
# 本 repo 為 public schema → 對現行 refund_requests 表加欄（migration 002，非破壞）。
# 舊 create_refund_request / submit_decision 雙簽流程保留做 legacy 過渡，不刪。
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_REFUND_CONFIG: dict = {
    "version_note": "ADR-0040 v2 defaults (5-tier 1k/5k/30k/100k + 三維 SoD)",
    # refund_class 合法值（對齊 saas.refund.refund_class CHECK）
    "refund_classes": ["product", "labor", "material", "travel", "inspection"],
    "tiers": {
        # 升冪門檻：amount <= thresholds[0] → L1；> thresholds[3] → L5（ADR-0040 §97-104）
        "thresholds": [1000, 5000, 30000, 100000],
        # 每 tier 的核准角色（最低有權核准者；高 tier 需更高層級）
        "approver_roles": {
            "L1": "supervisor",
            "L2": "manager",
            "L3": "finance_manager",
            "L4": "director",
            "L5": "cfo",
        },
        # 每 tier 要求的核准簽核人數（單調不遞減）
        "required_approvals": {
            "L1": 1,
            "L2": 1,
            "L3": 2,
            "L4": 2,
            "L5": 3,
        },
    },
}

_VALID_TERMINAL_REFUND_STATES = {"rejected", "executed"}


# ── PURE 規則函式（無 DB — 單元測試覆蓋）─────────────────────────────────────

def resolve_tier(amount: float, refund_config: dict) -> str:
    """伺服器端從金額推算 5-tier（ADR-0040 §97-104）。

    門檻來自 config（預設 1000/5000/30000/100000），邊界含於較低 tier：
      amount <= t0 → L1 ; t0 < amount <= t1 → L2 ; ... ; amount > t3 → L5。
    """
    thresholds = refund_config.get("tiers", {}).get("thresholds")
    if not thresholds or len(thresholds) != 4:
        raise ApiError("INTERNAL_ERROR", "refund tier thresholds misconfigured", 500)
    amt = float(amount)
    if amt <= thresholds[0]:
        return "L1"
    if amt <= thresholds[1]:
        return "L2"
    if amt <= thresholds[2]:
        return "L3"
    if amt <= thresholds[3]:
        return "L4"
    return "L5"


def validate_refund_class(refund_class: str | None) -> None:
    """refund_class 必填 + 須為合法 enum。

    缺 → 422 REFUND_CLASS_REQUIRED；非法值 → 422 REFUND_CLASS_INVALID。
    """
    if refund_class is None or not str(refund_class).strip():
        raise ApiError(
            "REFUND_CLASS_REQUIRED",
            "refund_class is required: one of product / labor / material / travel / inspection",
            422,
        )
    valid = set(DEFAULT_REFUND_CONFIG["refund_classes"])
    if refund_class not in valid:
        raise ApiError(
            "REFUND_CLASS_INVALID",
            f"invalid refund_class '{refund_class}'; expected one of {sorted(valid)}",
            422,
        )


def validate_amount(amount: float) -> None:
    """amount 必須 > 0，否則 422。"""
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_ERROR", "amount must be a number", 422)
    if amt <= 0:
        raise ApiError("VALIDATION_ERROR", "amount must be greater than 0", 422)


def approver_role_for_tier(tier: str, refund_config: dict) -> str | None:
    """查 tier 對應的最低核准角色（純函式）。"""
    return refund_config.get("tiers", {}).get("approver_roles", {}).get(tier)


# ── DB 編排 ──────────────────────────────────────────────────────────────────

_WO_TENANT_JOIN_REFUND = (
    "FROM work_orders wo "
    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "LEFT JOIN conversations c ON pc.conversation_id = c.id "
    "LEFT JOIN users u ON c.user_id = u.id"
)


async def _fetch_wo_tenant(work_order_id: str) -> str:
    """取 WO 所屬 tenant；NOT_FOUND if missing。"""
    cur = await db_module._conn.execute(
        f"SELECT u.tenant_id {_WO_TENANT_JOIN_REFUND} WHERE wo.id = %s::uuid",
        (work_order_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    return str(row[0])


async def create_refund_sod(
    *,
    tenant_id: str,
    work_order_id: str,
    amount: float,
    refund_class: str,
    reason: str,
    evidence_ids: list[str] | None,
    refund_config: dict,
    config_version: str,
    sod_initiator: str,
    sod_approver: str,
    sod_executor: str | None,
    actor_id: str,
    actor_role: str,
) -> dict:
    """三維 SoD + 5-tier 退款建立編排，回 RefundSodResult dict。

    呼叫端（router）已先驗 SoD headers（require_sod_actors）。此處再跑商業規則
    （amount>0、refund_class、tier 推算、check_sod 防禦性再驗）+ DB 寫入 + audit。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. PURE 驗證（amount / refund_class / SoD 防禦性再驗）
    validate_amount(amount)
    validate_refund_class(refund_class)
    check_sod(sod_initiator, sod_approver, sod_executor)

    # 2. 伺服器端推算 tier
    tier = resolve_tier(amount, refund_config)

    # 3. tenant guard（WO 必須屬於本 tenant）
    wo_tenant = await _fetch_wo_tenant(work_order_id)
    if wo_tenant != tenant_id:
        raise ApiError("NOT_FOUND", "Work order not found", 404)  # 跨 tenant 偽裝 404

    # 4. audit（三維行為人記於 payload）→ 取回 audit_event_id（NOT NULL）
    from services import audit_log_service

    audit_payload = {
        "operator_id": sod_initiator,
        "approver_id": sod_approver,
        "executor_id": sod_executor,
        "operator_role": actor_role,
        "amount": float(amount),
        "tier": tier,
        "refund_class": refund_class,
        "reason": reason,
        "evidence_ids": evidence_ids or [],
        "config_version_applied": config_version,
        "approver_role_required": approver_role_for_tier(tier, refund_config),
    }
    audit_event_id = await audit_log_service.log_event_returning_id(
        event_type="financial_action",
        actor_id=actor_id,
        actor_role=actor_role,
        action="refund.created",
        target_type="work_order",
        target_id=work_order_id,
        payload=audit_payload,
    )

    # 5. INSERT refund_requests row（新 SoD/tier 欄位 + 既有 amount/reason/status）
    approver_arr = [sod_approver] if sod_approver else []
    cur = await db_module._conn.execute(
        "INSERT INTO refund_requests "
        "  (work_order_id, requested_by, amount, reason, status, "
        "   tier, refund_class, initiator_user_id, approver_user_ids, "
        "   executor_user_id, audit_event_id, config_version_used) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'pending', "
        "        %s, %s, %s::uuid, %s::uuid[], "
        "        %s, %s::uuid, %s) "
        "RETURNING id",
        (
            work_order_id, actor_id, float(amount), reason,
            tier, refund_class, sod_initiator, approver_arr,
            sod_executor, audit_event_id, config_version,
        ),
    )
    new_row = await cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert refund request", 500)
    refund_id = str(new_row[0])

    return {
        "refund_id": refund_id,
        "work_order_id": work_order_id,
        "amount": f"{float(amount):.2f}",
        "tier": tier,
        "refund_class": refund_class,
        "state": "pending",
        "initiator_user_id": sod_initiator,
        "approver_user_ids": approver_arr,
        "executor_user_id": sod_executor,
        "audit_event_id": str(audit_event_id),
    }


async def get_refund_sod(*, tenant_id: str, refund_id: str) -> dict:
    """取單筆 SoD 退款（含 tenant guard），回 RefundSodResult dict。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT r.id, r.work_order_id, r.amount, r.tier, r.refund_class, r.status, "
        "       r.initiator_user_id, r.approver_user_ids, r.executor_user_id, r.audit_event_id "
        "FROM refund_requests r "
        "JOIN work_orders wo ON r.work_order_id = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE r.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid LIMIT 1",
        (refund_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Refund request {refund_id} not found", 404)
    return {
        "refund_id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "amount": _coerce_decimal(row[2]),
        "tier": row[3],
        "refund_class": row[4],
        "state": _coerce_status(row[5]),
        "initiator_user_id": str(row[6]) if row[6] else None,
        "approver_user_ids": [str(x) for x in (row[7] or [])],
        "executor_user_id": str(row[8]) if row[8] else None,
        "audit_event_id": str(row[9]) if row[9] else None,
    }
