"""Cancellation 6-stage v2 業務邏輯（ADR-0102 / FR-0052 / BR-CANCEL-001..008）。

spec-alignment 第一個 vertical slice。把取消從「只改 status」升級為完整 6 階段：
  S1 / S1_5 / S2 / S3 / S4 / S5 — 伺服器端推算階段 + 階段化費用 + reason code
  字典 + 師傅 initiated 三段政策 + goodwill_waiver override + SoD 三維 + audit。

設計：核心規則為 PURE 函式（無 DB，可單元測試）；DB 編排在
`cancel_work_order_6stage()`。費用 / reason code / 累犯閾值皆 configurable
（ADR-0067 §E，走 system_config 的 cancellation namespace）。

⚠ 現行 schema 無 quote_version 表 → S1_5 / S5 的精確判定（quote.customer_confirmed
／完工項目比例）以 reason_code 字典為權威來源 + WO 狀態機 best-effort 推算。
完整 quote lifecycle 接入見 gap audit §7 波次 P3。
"""

from __future__ import annotations

import logging
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service

logger = logging.getLogger("api.cancellation_service")


# ─────────────────────────────────────────────────────────────────────────────
# Default configurable plane (ADR-0102 §E)  — embed 到 system_config.cancellation
# ─────────────────────────────────────────────────────────────────────────────

# customer_fee 計算型別：
#   zero                                  → 0
#   s2_flat                               → 取消費 (s2_cancellation_fee)
#   travel_plus_cancel                    → 車馬費 + 取消費
#   travel_plus_inspection_plus_cancel    → 車馬費 + 檢測費 + 取消費
#   partial_formula                       → 工項總額 × 完工比例 + 車馬費
DEFAULT_CANCELLATION_CONFIG: dict[str, Any] = {
    # CR-0044：S3/S4 取消費校正為 esales 已決定值（SoT 衝突業主 2026-06-19 裁決採 esales）。
    # 來源：esales『03 區域與加價規則』CNL-S2/S3/S4=300/500/800（已知規格 ADR-0102，2026-06-03，較新）。
    "version_note": "ADR-0102 / esales 03 加價規則 2026-06-03（CR-0044 業主 2026-06-19 裁決 S3=500/S4=800）",
    "fees": {
        "s2_cancellation_fee": 300,
        "s3_cancellation_fee": 500,
        "s4_cancellation_fee": 800,
        "inspection_fee": 300,
        "travel_fee_min": 500,
        "travel_fee_max": 1200,
        "travel_fee_per_km": 20,
    },
    "technician_monthly_cancel_threshold": 2,  # 當月 ≥ 此次數開始扣 weight
    "technician_penalty_weight": 5,            # ADR-0102 §C weight -5
    "goodwill_approval_delta_pct": 50.0,       # 調整 > 此 % 或歸零需主管覆核
    # ADR-0102 §B reason code dictionary（四向分類）
    "reason_codes": {
        "quote_not_confirmed": {
            "stage": "S1", "fee_type": "zero", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "quote_confirmed_no_dispatch": {
            "stage": "S1_5", "fee_type": "zero", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "dispatched_not_departed": {
            "stage": "S2", "fee_type": "s2_flat", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "en_route_cancelled": {
            "stage": "S3", "fee_type": "travel_plus_cancel", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "customer_not_onsite": {
            "stage": "S3", "fee_type": "travel_plus_cancel", "initiator": "customer",
            "technician_penalty": False, "evidence_required": ["gps", "timestamp"],
        },
        "onsite_not_executed": {
            "stage": "S4", "fee_type": "travel_plus_inspection_plus_cancel",
            "initiator": "customer", "technician_penalty": False, "evidence_required": [],
        },
        "customer_refused": {
            "stage": "S4", "fee_type": "travel_plus_inspection_plus_cancel",
            "initiator": "customer", "technician_penalty": False, "evidence_required": [],
        },
        "partial_completed_cancel": {
            "stage": "S5", "fee_type": "partial_formula", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "customer_quote_rejected_after_dispatch": {
            "stage": "S5", "fee_type": "partial_formula", "initiator": "customer",
            "technician_penalty": False, "evidence_required": [],
        },
        "technician_initiated_cancel": {
            "stage": "any", "fee_type": "zero", "initiator": "technician",
            "technician_penalty": True, "evidence_required": ["contact_log_or_force_majeure_proof"],
        },
        "unpaid_no_response": {
            "stage": "any", "fee_type": "zero", "initiator": "system_auto",
            "technician_penalty": False, "evidence_required": [],
        },
        "business_cancel": {
            "stage": "any", "fee_type": "zero", "initiator": "customer_service",
            "technician_penalty": False, "evidence_required": [],
        },
    },
}

# stage 'any' 的 code → 由 WO 狀態映射到具體階段（無 quote 表時 best-effort）
_STATUS_TO_STAGE = {
    "created": "S1",
    "assigned": "S2",
    "accepted": "S3",
    "in_progress": "S4",
}

_VALID_STAGES = {"S1", "S1_5", "S2", "S3", "S4", "S5"}
_TERMINAL_STATUSES = {"completed", "confirmed", "cancelled"}
_VALID_INITIATOR_ROLES = {"customer", "customer_service", "technician", "system_auto"}


# ─────────────────────────────────────────────────────────────────────────────
# PURE 規則函式（無 DB — 單元測試覆蓋）
# ─────────────────────────────────────────────────────────────────────────────

def get_reason_entry(reason_code: str, cancellation_config: dict) -> dict:
    """查 reason code 字典；未知 → 422 REASON_CODE_UNKNOWN。"""
    entry = cancellation_config.get("reason_codes", {}).get(reason_code)
    if entry is None:
        raise ApiError(
            "REASON_CODE_UNKNOWN",
            f"Unknown cancellation reason_code '{reason_code}'",
            422,
        )
    return entry


def derive_stage(wo_status: str, reason_entry: dict) -> str:
    """伺服器端推算階段。reason_entry['stage'] 為明確階段時直接用；
    'any'（師傅／系統／業務側）→ 依 WO 狀態映射。"""
    stage = reason_entry.get("stage", "any")
    if stage in _VALID_STAGES:
        return stage
    return _STATUS_TO_STAGE.get(wo_status, "S1")


def _travel_fee(cancellation_config: dict, distance_km: float | None) -> float:
    fees = cancellation_config["fees"]
    lo = float(fees["travel_fee_min"])
    hi = float(fees["travel_fee_max"])
    if distance_km is None:
        return lo
    raw = lo + float(fees["travel_fee_per_km"]) * float(distance_km)
    return max(lo, min(hi, raw))


def compute_fees(
    stage: str,
    reason_entry: dict,
    cancellation_config: dict,
    *,
    base_amount: float | None,
    distance_km: float | None = None,
    completed_ratio: float | None = None,
) -> tuple[float, float]:
    """回 (customer_fee, travel_fee)。fee_type 決定計算方式（ADR-0102 §A/§B）。

    師傅／系統／業務側（fee_type=zero）一律客戶側 0。
    """
    fees = cancellation_config["fees"]
    fee_type = reason_entry.get("fee_type", "zero")
    base = float(base_amount or 0.0)

    if fee_type == "zero":
        return (0.0, 0.0)
    if fee_type == "s2_flat":
        return (float(fees["s2_cancellation_fee"]), 0.0)
    if fee_type == "travel_plus_cancel":
        return (float(fees["s3_cancellation_fee"]), _travel_fee(cancellation_config, distance_km))
    if fee_type == "travel_plus_inspection_plus_cancel":
        customer = float(fees["inspection_fee"]) + float(fees["s4_cancellation_fee"])
        return (customer, _travel_fee(cancellation_config, distance_km))
    if fee_type == "partial_formula":
        ratio = 1.0 if completed_ratio is None else max(0.0, min(1.0, float(completed_ratio)))
        return (round(base * ratio, 2), _travel_fee(cancellation_config, distance_km))

    # 未知 fee_type → 保守歸零（不誤收）
    logger.warning("unknown fee_type '%s'; defaulting to 0", fee_type)
    return (0.0, 0.0)


def compute_technician_penalty(prior_monthly_count: int, cancellation_config: dict) -> float:
    """師傅 initiated 累犯 penalty（ADR-0102 §C）。

    prior_monthly_count = 本次之前當月已發生次數。
    首次（prior=0）→ 免責 0；達門檻（prior ≥ threshold-1）→ 扣 weight。
    """
    threshold = int(cancellation_config.get("technician_monthly_cancel_threshold", 2))
    weight = float(cancellation_config.get("technician_penalty_weight", 5))
    # 這是「第 prior+1 次」。當 prior+1 >= threshold 時開始扣。
    return weight if (prior_monthly_count + 1) >= threshold else 0.0


def check_sod(initiator: str | None, approver: str | None, executor: str | None = None) -> None:
    """SoD 三維（BR-M17-01 / ADR-0102 §D）：initiator / approver / executor 任二相同 → 403。"""
    actors = [a for a in (initiator, approver, executor) if a]
    if len(actors) != len(set(actors)):
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: initiator / approver / executor must be distinct",
            403,
        )


def ensure_evidence(reason_entry: dict, evidence_ids: list[str] | None) -> None:
    """reason_code 要求 evidence 時必須提供（BR-M08-01）→ 否則 422 EVIDENCE_MISSING。"""
    required = reason_entry.get("evidence_required") or []
    if required and not evidence_ids:
        raise ApiError(
            "EVIDENCE_MISSING",
            f"reason_code requires evidence: {', '.join(required)}",
            422,
        )


def apply_goodwill(customer_fee: float, travel_fee: float, *, goodwill_waiver: bool) -> tuple[float, float]:
    """goodwill_waiver=true → 客服善意豁免，費用歸零（ADR-0102 §A 規則 2 / §B）。"""
    if goodwill_waiver:
        return (0.0, 0.0)
    return (customer_fee, travel_fee)


# ─────────────────────────────────────────────────────────────────────────────
# DB 編排
# ─────────────────────────────────────────────────────────────────────────────

# UAT-0718 P1-B 補刀：手建卡工單（pc.conversation_id=NULL）原 INNER JOIN 被剔除
# → 取消工單恆 404。LEFT 化 + tenant guard COALESCE(pc.tenant_id, u.tenant_id)
# （同上輪 26 檔同型修法）。
_WO_JOIN = (
    "FROM work_orders wo "
    "JOIN problem_cards pc ON pc.id = wo.problem_card_id "
    "LEFT JOIN conversations c ON c.id = pc.conversation_id "
    "LEFT JOIN users u ON u.id = c.user_id"
)


async def _fetch_wo_for_cancel(wo_id: str, tenant_id: str) -> dict:
    """取 WO 狀態 + 金額 + 技師，含 tenant guard。NOT_FOUND if missing。"""
    cur = await db_module._conn.execute(
        "SELECT wo.status, wo.final_price, wo.estimated_price, wo.technician_id "
        f"{_WO_JOIN} "
        "WHERE wo.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    return {
        "status": row[0],
        "final_price": row[1],
        "estimated_price": row[2],
        "technician_id": str(row[3]) if row[3] else None,
    }


async def _count_technician_monthly_cancels(technician_id: str, tenant_id: str) -> int:
    """本月該技師 technician_initiated_cancel 既有次數（不含本次）。"""
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) "
        "FROM cancellation cx "
        "JOIN work_orders wo ON wo.id = cx.work_order_id "
        "WHERE cx.tenant_id = %s::uuid "
        "  AND wo.technician_id = %s::uuid "
        "  AND cx.reason_code = 'technician_initiated_cancel' "
        "  AND date_trunc('month', cx.created_at) = date_trunc('month', CURRENT_TIMESTAMP)",
        (tenant_id, technician_id),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 0


async def cancel_work_order_6stage(
    *,
    tenant_id: str,
    wo_id: str,
    reason_code: str,
    initiator_role: str,
    goodwill_waiver: bool,
    evidence_ids: list[str] | None,
    note: str | None,
    distance_km: float | None,
    cancellation_config: dict,
    config_version: str,
    sod_initiator: str,
    sod_approver: str,
    sod_executor: str | None,
    actor_id: str,
    actor_role: str,
) -> dict:
    """完整 6 階段取消編排，回 CancellationResult dict。

    呼叫端（router）已先驗 SoD headers（check_sod）。此處再跑商業規則 +
    DB 寫入 + audit。terminal 狀態 → 409 WO_STATE_INVALID。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if initiator_role not in _VALID_INITIATOR_ROLES:
        raise ApiError("VALIDATION_ERROR", f"invalid initiator_role '{initiator_role}'", 422)

    # 1. reason code + evidence gate（PURE）
    reason_entry = get_reason_entry(reason_code, cancellation_config)
    ensure_evidence(reason_entry, evidence_ids)

    # 2. 取 WO + terminal guard
    wo = await _fetch_wo_for_cancel(wo_id, tenant_id)
    if wo["status"] in _TERMINAL_STATUSES:
        raise ApiError(
            "WO_STATE_INVALID",
            f"Cannot cancel work order in terminal status '{wo['status']}'",
            409,
        )

    # 3. 推算階段 + 費用（PURE）
    stage = derive_stage(wo["status"], reason_entry)
    base_amount = wo["final_price"] if wo["final_price"] is not None else wo["estimated_price"]
    customer_fee, travel_fee = compute_fees(
        stage, reason_entry, cancellation_config,
        base_amount=base_amount, distance_km=distance_km,
    )

    # 4. 師傅 initiated 累犯 penalty
    technician_penalty: float | None = None
    technician_monthly_count: int | None = None
    if reason_entry.get("technician_penalty") and wo["technician_id"]:
        prior = await _count_technician_monthly_cancels(wo["technician_id"], tenant_id)
        technician_monthly_count = prior + 1
        technician_penalty = compute_technician_penalty(prior, cancellation_config)

    # 5. goodwill 覆寫（主管 = approver，已由 SoD 保證 ≠ initiator）
    original_customer_fee = customer_fee
    customer_fee, travel_fee = apply_goodwill(customer_fee, travel_fee, goodwill_waiver=goodwill_waiver)
    delta_pct = 0.0
    if original_customer_fee > 0:
        delta_pct = (customer_fee - original_customer_fee) / original_customer_fee * 100.0

    # 6. audit（ADR-0102 §D 必填欄位）→ 取回 audit_event_id（cancellation.audit_event_id NOT NULL）
    audit_payload = {
        "operator_id": sod_initiator,        # SoD initiator (X-Initiator)
        "approver_id": sod_approver,         # SoD approver (X-Approver)
        "executor_id": sod_executor,         # SoD executor (X-Executor)
        "operator_role": actor_role,
        "original_amount": original_customer_fee,
        "new_amount": customer_fee,
        "delta_pct": round(delta_pct, 2),
        "reason_code": reason_code,
        "supervisor_approval_id": sod_approver if goodwill_waiver else None,
        "evidence_ids": evidence_ids or [],
        "config_version_applied": config_version,
        "cancellation_stage": stage,
        "technician_initiated": initiator_role == "technician",
        "technician_monthly_count": technician_monthly_count,
        "travel_fee": travel_fee,
        "technician_penalty": technician_penalty,
    }
    audit_event_id = await audit_log_service.log_event_returning_id(
        event_type="financial_action",
        actor_id=actor_id,
        actor_role=actor_role,
        action="cancellation.posted",
        target_type="work_order",
        target_id=wo_id,
        payload=audit_payload,
    )

    # 7. 寫 cancellation row + 更新 WO 狀態
    await db_module._conn.execute(
        "INSERT INTO cancellation "
        "(tenant_id, work_order_id, cancellation_stage, initiator_role, reason_code, "
        " customer_fee, travel_fee, technician_penalty, goodwill_waiver, "
        " audit_event_id, config_version_used, note) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, "
        "        %s::uuid, %s, %s)",
        (
            tenant_id, wo_id, stage, initiator_role, reason_code,
            customer_fee, travel_fee, technician_penalty, goodwill_waiver,
            audit_event_id, config_version, note,
        ),
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'cancelled', "
        "  service_report = COALESCE(service_report, '') || E'\\n[CANCELLED:' || %s || '] ' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (stage, reason_code, wo_id),
    )
    # CR-0193：生命週期事件。這條容易被漏——v2 tenant-scoped 取消走本服務（ADR-0102
    # 六階段＋費用），**不經** work_order_service.cancel_order（那條只剩 legacy flat
    # /api/v1/work-orders/{id}/cancel 在用）。只補 cancel_order 的話，實際在用的取消
    # 路徑仍然不落事件 → timeline 看不到「取消」。
    from services.work_order_service import _insert_wo_event

    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_id,
        event_type="cancelled",
        payload={
            "from_status": wo["status"],
            "cancellation_stage": stage,
            "reason_code": reason_code,
            "initiator_role": initiator_role,
            "customer_fee": str(customer_fee),
            "travel_fee": str(travel_fee),
            "technician_penalty": str(technician_penalty),
            "goodwill_waiver": goodwill_waiver,
            "audit_event_id": str(audit_event_id),
        },
    )

    return {
        "work_order_id": wo_id,
        "cancellation_stage": stage,
        "customer_fee": customer_fee,
        "travel_fee": travel_fee,
        "technician_penalty": technician_penalty,
        "reason_code": reason_code,
        "audit_event_id": str(audit_event_id),
    }
