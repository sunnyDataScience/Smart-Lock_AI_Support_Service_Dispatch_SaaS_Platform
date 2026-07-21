"""audit FR-API-05：派工評分五因子——負載(load)/公平(fairness) 補洞。

補洞前只有 skill/distance/rating 三因子；此測試鎖定新增的 load/fairness
純評分函式與權重和=1.0（不碰 DB）。
"""

from __future__ import annotations

from services.dispatch_service import (
    _MIN_DISPATCH_POOL,
    _W_DISTANCE,
    _W_FAIRNESS,
    _W_LOAD,
    _W_RATING,
    _W_SKILL,
    _apply_progressive_radius,
    _fairness_factor,
    _load_factor,
)


def _cand(km):
    return {"gis_distance_km": km, "technician": {"id": f"t-{km}"}}


def test_progressive_radius_stops_at_5km_when_enough():
    cands = [_cand(1), _cand(2), _cand(3), _cand(8), _cand(15)]  # 3 個 ≤5km
    out = _apply_progressive_radius(cands, min_pool=3)
    assert len(out) == 3
    assert all(c["radius_band_km"] == 5.0 for c in out)


def test_progressive_radius_expands_to_10km():
    cands = [_cand(2), _cand(8), _cand(9), _cand(25)]  # 只 1 個 ≤5，≤10 有 3 個
    out = _apply_progressive_radius(cands, min_pool=3)
    assert len(out) == 3  # 2/8/9
    assert {c["gis_distance_km"] for c in out} == {2, 8, 9}


def test_progressive_radius_falls_back_to_all_when_no_coords():
    cands = [_cand(None), _cand(None)]  # 無座標 → 三級皆不足 → 全納
    out = _apply_progressive_radius(cands, min_pool=3)
    assert len(out) == 2
    assert all(c["radius_band_km"] is None for c in out)


def test_progressive_radius_default_min_pool():
    assert _MIN_DISPATCH_POOL == 3


def test_weights_sum_to_one():
    total = _W_SKILL + _W_DISTANCE + _W_RATING + _W_LOAD + _W_FAIRNESS
    assert abs(total - 1.0) < 1e-9


def test_load_factor_monotonic_decreasing():
    assert _load_factor(0) == 1.0        # 空閒滿分
    assert _load_factor(5) == 0.0        # 滿載歸零
    assert _load_factor(None) == 0.5     # 查無 → 中性
    assert _load_factor(1) > _load_factor(3) > _load_factor(4)
    # 超過飽和值仍夾在 0
    assert _load_factor(10) == 0.0


def test_fairness_factor_monotonic_decreasing():
    assert _fairness_factor(0) == 1.0        # 近期沒接單 → 優先派
    assert _fairness_factor(None) == 0.5     # 查無 → 中性
    assert _fairness_factor(1) > _fairness_factor(5)
    # 負值防禦（不應發生）夾到 0 次
    assert _fairness_factor(-3) == 1.0
