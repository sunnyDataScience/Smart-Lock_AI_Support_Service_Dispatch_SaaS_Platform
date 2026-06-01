"""Warranty 5-mode 保固起算單元測試（ADR-0044 v2 / FR-0015 / BR-WARRANTY-001..007）。

聚焦純函式（無 DB）：6 種 warranty_start_mode 取對錨點、period_months 推算到期日、
保固邊界判定（claim_date == end_date 仍在保）、RMA 重算（延長 / 換主鎖獨立保固）、
B2B override 上限 60 個月驗證。

整合測試（需 live DB）放在 test_device_warranty_endpoint.py（gated）；本檔保證
核心起算規則可在無 DB 環境穩定 RED→GREEN。

ADR-0044 v2 正典 warranty_start_mode enum（非舊版 purchase/handover/activation）：
  purchase_date / install_date / handover_date /
  brand_warranty_date / contract_date / manual_override
"""

from __future__ import annotations

from datetime import date

import pytest

from core.errors import ApiError
from services import warranty_service as ws

pytestmark = pytest.mark.unit

CFG = ws.DEFAULT_WARRANTY_CONFIG


# 各 mode 對應的錨點日期樣本（彼此不同，方便驗證取對欄位）
_PURCHASE = date(2026, 1, 1)
_INSTALL = date(2026, 2, 1)
_HANDOVER = date(2026, 3, 1)
_BRAND = date(2026, 4, 1)
_CONTRACT = date(2026, 5, 1)


def _all_anchors() -> dict:
    return {
        "purchase_date": _PURCHASE,
        "install_date": _INSTALL,
        "handover_date": _HANDOVER,
        "brand_warranty_date": _BRAND,
        "contract_date": _CONTRACT,
    }


# ── DEFAULT_WARRANTY_CONFIG 形狀 ─────────────────────────────────────────────

def test_default_config_period_is_24():
    assert CFG["default_period_months"] == 24


def test_default_config_b2b_override_cap_is_60():
    assert CFG["b2b_override_max_months"] == 60


def test_valid_modes_are_adr0044_v2_canonical():
    modes = set(CFG["valid_start_modes"])
    assert modes == {
        "purchase_date",
        "install_date",
        "handover_date",
        "brand_warranty_date",
        "contract_date",
        "manual_override",
    }


# ── resolve_start_date：每個 mode 取對錨點 ──────────────────────────────────

def test_resolve_purchase_date_mode():
    assert ws.resolve_start_date("purchase_date", **_all_anchors()) == _PURCHASE


def test_resolve_install_date_mode():
    assert ws.resolve_start_date("install_date", **_all_anchors()) == _INSTALL


def test_resolve_handover_date_mode():
    assert ws.resolve_start_date("handover_date", **_all_anchors()) == _HANDOVER


def test_resolve_brand_warranty_date_mode():
    assert ws.resolve_start_date("brand_warranty_date", **_all_anchors()) == _BRAND


def test_resolve_contract_date_mode():
    assert ws.resolve_start_date("contract_date", **_all_anchors()) == _CONTRACT


def test_resolve_missing_anchor_raises_422():
    # handover_date mode 但沒給 handover_date → 缺資料 422
    with pytest.raises(ApiError) as ei:
        ws.resolve_start_date(
            "handover_date",
            purchase_date=_PURCHASE,
            install_date=None,
            handover_date=None,
            brand_warranty_date=None,
            contract_date=None,
        )
    assert ei.value.status_code == 422


def test_resolve_manual_override_requires_explicit_start():
    # manual_override 不從錨點推 → 需人工指定（本函式不接受，回 422 引導走 PATCH 流程）
    with pytest.raises(ApiError) as ei:
        ws.resolve_start_date("manual_override", **_all_anchors())
    assert ei.value.status_code == 422


def test_resolve_unknown_mode_422():
    with pytest.raises(ApiError) as ei:
        ws.resolve_start_date("activation", **_all_anchors())
    assert ei.value.error_code == "WARRANTY_MODE_UNKNOWN"
    assert ei.value.status_code == 422


# ── compute_warranty_end：起算日 + period_months ────────────────────────────

def test_compute_end_24_months():
    # 2026-01-01 + 24 months = 2028-01-01
    assert ws.compute_warranty_end(date(2026, 1, 1), 24) == date(2028, 1, 1)


def test_compute_end_36_months():
    assert ws.compute_warranty_end(date(2026, 1, 1), 36) == date(2029, 1, 1)


def test_compute_end_month_overflow_normalizes():
    # 2026-03-15 + 24 months = 2028-03-15
    assert ws.compute_warranty_end(date(2026, 3, 15), 24) == date(2028, 3, 15)


def test_compute_end_handles_day_clamp():
    # 起算 2026-01-31 + 1 month 應 clamp 到 2 月底（非 day overflow）
    assert ws.compute_warranty_end(date(2026, 1, 31), 1) == date(2026, 2, 28)


# ── is_within_warranty：邊界 = 仍在保（BR-WARRANTY-003）─────────────────────

def test_within_warranty_before_end():
    assert ws.is_within_warranty(date(2027, 6, 1), date(2028, 1, 1)) is True


def test_within_warranty_boundary_equal_is_true():
    # claim_date == warranty_end_date → 仍視為在保固內
    assert ws.is_within_warranty(date(2028, 1, 1), date(2028, 1, 1)) is True


def test_within_warranty_one_day_after_is_false():
    assert ws.is_within_warranty(date(2028, 1, 2), date(2028, 1, 1)) is False


# ── recalc_after_rma（BR-WARRANTY-005）──────────────────────────────────────

def test_recalc_rma_extends_by_repair_days():
    # 被修期間延長：end += (rma_out - rma_in) days
    end = date(2028, 1, 1)
    new_end = ws.recalc_after_rma(
        end,
        rma_in=date(2026, 6, 1),
        rma_out=date(2026, 6, 11),  # 修了 10 天
        replaced_main_lock=False,
        rma_complete_date=date(2026, 6, 11),
    )
    assert new_end == date(2028, 1, 11)


def test_recalc_rma_replaced_main_lock_fresh_warranty():
    # 換新主鎖：從 RMA 完工日起算原期（period_months）+ 90 天獨立保固
    # 原期以 end - 推不出；spec：完工日 + 原 period + 90 天。
    # 以 default 24 個月 + 90 天表示：complete 2026-06-11 + 24m = 2028-06-11, +90d = 2028-09-09
    end = date(2028, 1, 1)
    new_end = ws.recalc_after_rma(
        end,
        rma_in=date(2026, 6, 1),
        rma_out=date(2026, 6, 11),
        replaced_main_lock=True,
        rma_complete_date=date(2026, 6, 11),
        period_months=24,
    )
    assert new_end == date(2028, 9, 9)


# ── validate_b2b_override（BR-WARRANTY-006）─────────────────────────────────

def test_b2b_override_60_ok():
    ws.validate_b2b_override(60)  # no raise


def test_b2b_override_under_cap_ok():
    ws.validate_b2b_override(36)  # no raise


def test_b2b_override_61_raises_422():
    with pytest.raises(ApiError) as ei:
        ws.validate_b2b_override(61)
    assert ei.value.error_code == "WARRANTY_OVERRIDE_EXCEEDS_CAP"
    assert ei.value.status_code == 422


def test_b2b_override_zero_or_negative_422():
    with pytest.raises(ApiError):
        ws.validate_b2b_override(0)
    with pytest.raises(ApiError):
        ws.validate_b2b_override(-5)


# ── select_period / site_group 繼承（純函式）────────────────────────────────

def test_resolve_period_brand_override():
    # 品牌 override map 命中 → 用 override
    assert ws.resolve_period_months("Yale", CFG) == CFG["brand_period_overrides"]["Yale"]


def test_resolve_period_default_when_no_override():
    assert ws.resolve_period_months("UnknownBrand", CFG) == 24


def test_select_inherit_from_site_group_true_uses_group_mode():
    # 建商案件 inherit=True → 採 site_group 的 mode
    result = ws.select_warranty_source(
        inherit_from_site_group=True,
        site_group_mode="handover_date",
        device_mode="purchase_date",
    )
    assert result == "handover_date"


def test_select_inherit_false_uses_device_mode():
    result = ws.select_warranty_source(
        inherit_from_site_group=False,
        site_group_mode="handover_date",
        device_mode="purchase_date",
    )
    assert result == "purchase_date"
