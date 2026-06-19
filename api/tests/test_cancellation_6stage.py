"""Cancellation 6-stage v2 單元測試（ADR-0102 / FR-0052 / AC-V11-08）。

聚焦純函式（無 DB）：階段推算、6 階段費用、SoD 三維、師傅 initiated penalty、
reason code 驗證、evidence gate、goodwill_waiver。對齊 spec 對打場景 CNL-S1..S5。

整合測試（需 live DB）放在 test_cancellation_endpoint.py（gated）；本檔保證
核心商業規則可在無 DB 環境穩定 RED→GREEN。
"""

from __future__ import annotations

import pytest

from core.errors import ApiError
from services import cancellation_service as cs

pytestmark = pytest.mark.unit

CFG = cs.DEFAULT_CANCELLATION_CONFIG


# ── reason code 字典 ────────────────────────────────────────────────────────

def test_reason_dictionary_has_adr0102_codes():
    codes = CFG["reason_codes"]
    for code in [
        "quote_not_confirmed",
        "quote_confirmed_no_dispatch",
        "dispatched_not_departed",
        "en_route_cancelled",
        "customer_not_onsite",
        "onsite_not_executed",
        "customer_refused",
        "partial_completed_cancel",
        "customer_quote_rejected_after_dispatch",
        "technician_initiated_cancel",
        "unpaid_no_response",
        "business_cancel",
    ]:
        assert code in codes, f"missing reason_code {code}"


def test_get_reason_entry_known():
    entry = cs.get_reason_entry("dispatched_not_departed", CFG)
    assert entry["stage"] == "S2"


def test_get_reason_entry_unknown_422():
    with pytest.raises(ApiError) as ei:
        cs.get_reason_entry("does_not_exist", CFG)
    assert ei.value.error_code == "REASON_CODE_UNKNOWN"
    assert ei.value.status_code == 422


# ── 階段推算 ────────────────────────────────────────────────────────────────

def test_derive_stage_explicit():
    assert cs.derive_stage("assigned", cs.get_reason_entry("dispatched_not_departed", CFG)) == "S2"
    assert cs.derive_stage("created", cs.get_reason_entry("quote_not_confirmed", CFG)) == "S1"
    assert cs.derive_stage("in_progress", cs.get_reason_entry("partial_completed_cancel", CFG)) == "S5"


def test_derive_stage_any_code_from_status():
    # technician_initiated_cancel = stage 'any' → 由 WO 狀態映射
    entry = cs.get_reason_entry("technician_initiated_cancel", CFG)
    assert cs.derive_stage("created", entry) == "S1"
    assert cs.derive_stage("assigned", entry) == "S2"
    assert cs.derive_stage("accepted", entry) == "S3"
    assert cs.derive_stage("in_progress", entry) == "S4"


# ── 6 階段費用 ──────────────────────────────────────────────────────────────

def test_fee_s1_and_s1_5_zero():
    assert cs.compute_fees("S1", cs.get_reason_entry("quote_not_confirmed", CFG), CFG, base_amount=2000) == (0.0, 0.0)
    assert cs.compute_fees("S1_5", cs.get_reason_entry("quote_confirmed_no_dispatch", CFG), CFG, base_amount=2000) == (0.0, 0.0)


def test_fee_s2_is_300():
    customer_fee, travel = cs.compute_fees(
        "S2", cs.get_reason_entry("dispatched_not_departed", CFG), CFG, base_amount=2000
    )
    assert customer_fee == 300.0
    assert travel == 0.0


def test_fee_s3_travel_plus_cancel():
    customer_fee, travel = cs.compute_fees(
        "S3", cs.get_reason_entry("en_route_cancelled", CFG), CFG, base_amount=2000, distance_km=None
    )
    assert customer_fee == 500.0  # CR-0044：S3 取消費 300→500（esales 已知規格）
    assert travel == 500.0  # travel_fee_min default


def test_fee_s4_inspection_plus_cancel():
    customer_fee, travel = cs.compute_fees(
        "S4", cs.get_reason_entry("onsite_not_executed", CFG), CFG, base_amount=2000
    )
    # CR-0044：檢測費 300 + 取消費 800（S4，esales 已知規格）= 1100
    assert customer_fee == 1100.0
    assert travel == 500.0


def test_fee_s5_partial_formula():
    customer_fee, travel = cs.compute_fees(
        "S5",
        cs.get_reason_entry("partial_completed_cancel", CFG),
        CFG,
        base_amount=2000,
        completed_ratio=0.5,
    )
    # partial = 工項總額 × 完工比例 = 2000 * 0.5 = 1000 + 車馬
    assert customer_fee == 1000.0
    assert travel == 500.0


def test_travel_fee_scales_and_clamps():
    entry = cs.get_reason_entry("en_route_cancelled", CFG)
    _, t_far = cs.compute_fees("S3", entry, CFG, base_amount=2000, distance_km=100)
    assert t_far == CFG["fees"]["travel_fee_max"]  # clamp upper
    _, t_near = cs.compute_fees("S3", entry, CFG, base_amount=2000, distance_km=0)
    assert t_near == CFG["fees"]["travel_fee_min"]  # clamp lower


# ── 師傅 initiated（客戶側 fee=0 + 累犯 penalty）─────────────────────────────

def test_technician_initiated_customer_fee_zero():
    entry = cs.get_reason_entry("technician_initiated_cancel", CFG)
    customer_fee, travel = cs.compute_fees("S2", entry, CFG, base_amount=2000)
    assert customer_fee == 0.0
    assert travel == 0.0


def test_technician_penalty_first_time_zero():
    # 當月第 1 次（prior count = 0）→ 免責
    assert cs.compute_technician_penalty(0, CFG) == 0.0


def test_technician_penalty_repeat_charged():
    # 當月第 ≥2 次（prior count >= 1）→ 扣 weight
    assert cs.compute_technician_penalty(1, CFG) == float(CFG["technician_penalty_weight"])
    assert cs.compute_technician_penalty(3, CFG) == float(CFG["technician_penalty_weight"])


# ── SoD 三維 ────────────────────────────────────────────────────────────────

def test_sod_initiator_equals_approver_403():
    with pytest.raises(ApiError) as ei:
        cs.check_sod("user-a", "user-a", None)
    assert ei.value.error_code == "SOD_VIOLATION"
    assert ei.value.status_code == 403


def test_sod_distinct_ok():
    cs.check_sod("user-a", "user-b", None)  # no raise
    cs.check_sod("user-a", "user-b", "user-c")  # no raise


def test_sod_executor_collision_403():
    with pytest.raises(ApiError) as ei:
        cs.check_sod("user-a", "user-b", "user-a")
    assert ei.value.error_code == "SOD_VIOLATION"


# ── evidence gate（BR-M08-01）───────────────────────────────────────────────

def test_evidence_required_missing_422():
    entry = cs.get_reason_entry("customer_not_onsite", CFG)
    with pytest.raises(ApiError) as ei:
        cs.ensure_evidence(entry, [])
    assert ei.value.error_code == "EVIDENCE_MISSING"
    assert ei.value.status_code == 422


def test_evidence_present_ok():
    entry = cs.get_reason_entry("customer_not_onsite", CFG)
    cs.ensure_evidence(entry, ["gps:25.0,121.5", "ts:2026-06-01T10:00:00Z"])  # no raise


def test_evidence_not_required_passes_without():
    entry = cs.get_reason_entry("dispatched_not_departed", CFG)
    cs.ensure_evidence(entry, [])  # no raise


# ── goodwill_waiver ─────────────────────────────────────────────────────────

def test_goodwill_waiver_zeros_fee():
    assert cs.apply_goodwill(300.0, 500.0, goodwill_waiver=True) == (0.0, 0.0)


def test_goodwill_waiver_false_keeps_fee():
    assert cs.apply_goodwill(300.0, 500.0, goodwill_waiver=False) == (300.0, 500.0)
