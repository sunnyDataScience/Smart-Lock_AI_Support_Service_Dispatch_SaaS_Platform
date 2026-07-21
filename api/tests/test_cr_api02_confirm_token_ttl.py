"""FR-API-02：confirm_token TTL 上限 48h（_ttl_days_from 純函式）。

補洞前 TTL 對齊報價有效期（可達 7 天 fallback）；FR-API-02 要求 confirm_token TTL=48h。
此測試鎖定「取 min(報價有效期, 48h)、至少 1 天」的上限邏輯（純函式，不碰 DB）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.quote_engine_service import _CONFIRM_TOKEN_MAX_DAYS, _ttl_days_from


def test_cap_max_48h():
    assert _CONFIRM_TOKEN_MAX_DAYS == 2


def test_none_expiry_falls_back_capped():
    # fallback 7 天但受 48h 上限 → 2
    assert _ttl_days_from(None) == 2


def test_long_quote_capped_to_48h():
    far = datetime.now(timezone.utc) + timedelta(days=10)
    assert _ttl_days_from(far) == 2   # 報價有效 10 天，token 仍上限 48h


def test_short_quote_not_below_1_day():
    soon = datetime.now(timezone.utc) + timedelta(hours=6)
    assert _ttl_days_from(soon) == 1   # ceil(0.25)=1，未被上限影響


def test_expired_quote_min_1_day():
    past = datetime.now(timezone.utc) - timedelta(days=3)
    assert _ttl_days_from(past) == 1
