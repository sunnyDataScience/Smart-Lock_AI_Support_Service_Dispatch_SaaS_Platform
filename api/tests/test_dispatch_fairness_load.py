"""audit FR-API-05：派工評分五因子——負載(load)/公平(fairness) 補洞。

補洞前只有 skill/distance/rating 三因子；此測試鎖定新增的 load/fairness
純評分函式與權重和=1.0（不碰 DB）。
"""

from __future__ import annotations

from services.dispatch_service import (
    _W_DISTANCE,
    _W_FAIRNESS,
    _W_LOAD,
    _W_RATING,
    _W_SKILL,
    _fairness_factor,
    _load_factor,
)


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
