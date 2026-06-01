"""Refund 三維 SoD + 5-tier 單元測試（ADR-0040 v2 / BR-REFUND-006 / FR-0014）。

聚焦純函式（無 DB）：金額分級 resolve_tier 邊界、refund_class 驗證、amount 驗證、
三維 SoD（重用 cancellation_service.check_sod）。對齊 spec ADR-0040 §97-104
門檻 1k / 5k / 30k / 100k。

整合測試（需 live DB）放在 test_refund_sod_endpoint.py（gated）；本檔保證核心
商業規則可在無 DB 環境穩定 RED→GREEN。
"""

from __future__ import annotations

import pytest

from core.errors import ApiError
from services import refund_service as rs

pytestmark = pytest.mark.unit

CFG = rs.DEFAULT_REFUND_CONFIG


# ── 5-tier 金額分級（ADR-0040 §97-104，門檻 1000/5000/30000/100000）────────────

@pytest.mark.parametrize(
    "amount,expected",
    [
        (0.01, "L1"),
        (500, "L1"),
        (1000, "L1"),       # 邊界：≤1000 → L1
        (1000.0, "L1"),
        (1001, "L2"),       # 邊界：>1000 → L2
        (3000, "L2"),
        (5000, "L2"),       # 邊界：≤5000 → L2
        (5001, "L3"),       # 邊界：>5000 → L3
        (20000, "L3"),
        (30000, "L3"),      # 邊界：≤30000 → L3
        (30001, "L4"),      # 邊界：>30000 → L4
        (80000, "L4"),
        (100000, "L4"),     # 邊界：≤100000 → L4
        (100001, "L5"),     # 邊界：>100000 → L5
        (250000, "L5"),
    ],
)
def test_resolve_tier_boundaries(amount, expected):
    assert rs.resolve_tier(amount, CFG) == expected


def test_resolve_tier_uses_config_thresholds():
    # 自訂門檻時應跟著走（純函式，門檻來自 config）
    custom = {"tiers": {"thresholds": [10, 20, 30, 40]}}
    assert rs.resolve_tier(5, custom) == "L1"
    assert rs.resolve_tier(10, custom) == "L1"
    assert rs.resolve_tier(11, custom) == "L2"
    assert rs.resolve_tier(40, custom) == "L4"
    assert rs.resolve_tier(41, custom) == "L5"


# ── refund_class 驗證 ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "rc", ["product", "labor", "material", "travel", "inspection"]
)
def test_validate_refund_class_valid(rc):
    rs.validate_refund_class(rc)  # no raise


def test_validate_refund_class_missing_422():
    for missing in (None, "", "   "):
        with pytest.raises(ApiError) as ei:
            rs.validate_refund_class(missing)
        assert ei.value.error_code == "REFUND_CLASS_REQUIRED"
        assert ei.value.status_code == 422


def test_validate_refund_class_invalid_422():
    with pytest.raises(ApiError) as ei:
        rs.validate_refund_class("bogus_class")
    assert ei.value.error_code == "REFUND_CLASS_INVALID"
    assert ei.value.status_code == 422


def test_refund_class_enum_in_config():
    enum = CFG["refund_classes"]
    assert set(enum) == {"product", "labor", "material", "travel", "inspection"}


# ── amount 驗證（> 0）─────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [0, -1, -0.01, -100])
def test_validate_amount_non_positive_422(bad):
    with pytest.raises(ApiError) as ei:
        rs.validate_amount(bad)
    assert ei.value.error_code == "VALIDATION_ERROR"
    assert ei.value.status_code == 422


@pytest.mark.parametrize("ok", [0.01, 1, 1000, 999999])
def test_validate_amount_positive_ok(ok):
    rs.validate_amount(ok)  # no raise


# ── 三維 SoD（重用 cancellation_service.check_sod）────────────────────────────

def test_sod_initiator_equals_approver_403():
    with pytest.raises(ApiError) as ei:
        rs.check_sod("user-a", "user-a", None)
    assert ei.value.error_code == "SOD_VIOLATION"
    assert ei.value.status_code == 403


def test_sod_initiator_equals_executor_403():
    with pytest.raises(ApiError) as ei:
        rs.check_sod("user-a", "user-b", "user-a")
    assert ei.value.error_code == "SOD_VIOLATION"


def test_sod_approver_equals_executor_403():
    with pytest.raises(ApiError) as ei:
        rs.check_sod("user-a", "user-b", "user-b")
    assert ei.value.error_code == "SOD_VIOLATION"


def test_sod_all_distinct_ok():
    rs.check_sod("user-a", "user-b", None)          # no executor → ok
    rs.check_sod("user-a", "user-b", "user-c")      # all distinct → ok


def test_check_sod_is_reused_from_cancellation_service():
    # 鐵律：不得自己重寫 SoD，必須重用 P1-A primitive
    from services.cancellation_service import check_sod as cancel_check_sod
    assert rs.check_sod is cancel_check_sod


# ── approver 角色 mapping（每 tier 對應簽核角色）──────────────────────────────

def test_approver_roles_cover_all_tiers():
    roles = CFG["tiers"]["approver_roles"]
    for tier in ("L1", "L2", "L3", "L4", "L5"):
        assert tier in roles, f"missing approver role mapping for {tier}"
        assert roles[tier], f"empty approver role for {tier}"


def test_required_approvals_escalates_with_tier():
    # 高 tier 要求更多簽核人數（單調不遞減）
    counts = CFG["tiers"]["required_approvals"]
    seq = [counts[t] for t in ("L1", "L2", "L3", "L4", "L5")]
    assert seq == sorted(seq), "required_approvals must be monotonic non-decreasing"
    assert counts["L1"] >= 1
