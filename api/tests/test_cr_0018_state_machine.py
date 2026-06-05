"""CR-0018 Stage 3 — service 狀態機 / validation 純函式測試。

純邏輯不依賴 DB：
- _ALLOWED_TRANSITIONS 完整性
- _check_transition 拒非法轉移 (409)
- _VALID_KIND / _VALID_FIX_PATH / _VALID_DETECTED_BY enum 同 SQL schema
"""

from __future__ import annotations

import pytest

from services import reconciliation_exception_service as svc


# ----------------------------- enum 完整性 -----------------------------

def test_exception_kind_enum_matches_schema():
    """schema CHECK 與 _VALID_KIND 必須一致 — schema drift 預警。"""
    assert svc._VALID_KIND == {
        "amount_mismatch", "missing_invoice", "duplicate_entry",
        "orphan_settlement", "other",
    }


def test_fix_path_enum_matches_schema():
    assert svc._VALID_FIX_PATH == {
        "invoice_supplement", "recon_void", "voucher_reverse",
    }


def test_detected_by_enum_matches_schema():
    assert svc._VALID_DETECTED_BY == {
        "upload_realtime", "cron_daily", "manual",
    }


# ----------------------------- 狀態機 -----------------------------

def test_state_machine_six_states():
    """HD-2 六態應全部出現在 _ALLOWED_TRANSITIONS。"""
    expected = {
        "detected", "ops_review", "fix_proposed", "fix_approved",
        "applied", "closed",
    }
    assert set(svc._ALLOWED_TRANSITIONS.keys()) == expected


def test_state_machine_closed_is_terminal():
    """closed 無 outgoing transitions（終態）。"""
    assert svc._ALLOWED_TRANSITIONS["closed"] == set()


def test_state_machine_happy_path_intact():
    """detected → ops_review → fix_proposed → fix_approved → applied → closed
    完整 happy path 每一跳都應在 allowed map 中。"""
    path = [
        "detected", "ops_review", "fix_proposed",
        "fix_approved", "applied", "closed",
    ]
    for a, b in zip(path, path[1:]):
        assert b in svc._ALLOWED_TRANSITIONS[a], (
            f"missing transition {a} → {b}"
        )


def test_state_machine_misreport_path():
    """detected → closed 直接結案（誤報）路徑。"""
    assert "closed" in svc._ALLOWED_TRANSITIONS["detected"]
    assert "closed" in svc._ALLOWED_TRANSITIONS["ops_review"]


def test_state_machine_proposed_can_bounce_back():
    """fix_proposed → ops_review 退回路徑（HD-2 流程包含退件）。"""
    assert "ops_review" in svc._ALLOWED_TRANSITIONS["fix_proposed"]


def test_check_transition_allows_valid():
    """各 happy path 跳轉不該 raise。"""
    svc._check_transition("detected", "ops_review")
    svc._check_transition("fix_proposed", "fix_approved")
    svc._check_transition("applied", "closed")


def test_check_transition_rejects_invalid():
    """非法跳轉應 raise STATE_CONFLICT 409。"""
    from core.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        svc._check_transition("detected", "applied")  # skip steps
    assert exc_info.value.error_code == "STATE_CONFLICT"
    assert exc_info.value.status_code == 409


def test_check_transition_rejects_closed_outgoing():
    """closed 終態不可再轉。"""
    from core.errors import ApiError

    with pytest.raises(ApiError):
        svc._check_transition("closed", "applied")


def test_check_transition_rejects_unknown_source():
    """未知 status 應視同無 allowed 跳轉。"""
    from core.errors import ApiError

    with pytest.raises(ApiError):
        svc._check_transition("invalid_state", "closed")


# ----------------------------- coerce_decimal -----------------------------

def test_coerce_decimal_none():
    assert svc._coerce_decimal(None) is None


def test_coerce_decimal_int():
    assert svc._coerce_decimal(100) == "100.00"


def test_coerce_decimal_float():
    assert svc._coerce_decimal(-50.5) == "-50.50"
