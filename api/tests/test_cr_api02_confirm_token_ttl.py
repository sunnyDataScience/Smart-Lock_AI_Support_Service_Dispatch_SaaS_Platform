"""confirm_token TTL 上限 7 天（_ttl_days_from 純函式）。

FR-API-02 原合約 TTL=48h；CR-0181（0723 會議決議＋業主裁決）改為 7 天——
客戶常隔數日才回應，48h 連結先死造成流程卡住。
此測試鎖定「取 min(報價有效期, 7d)、至少 1 天」的上限邏輯（純函式，不碰 DB）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.quote_engine_service import _CONFIRM_TOKEN_MAX_DAYS, _ttl_days_from


def test_cap_max_7_days():
    assert _CONFIRM_TOKEN_MAX_DAYS == 7


def test_none_expiry_falls_back_capped():
    # fallback 7 天，與上限 7 天取 min → 7
    assert _ttl_days_from(None) == 7


def test_long_quote_capped_to_7_days():
    far = datetime.now(timezone.utc) + timedelta(days=30)
    assert _ttl_days_from(far) == 7   # 報價有效 30 天，token 仍上限 7 天


def test_quote_within_cap_follows_expiry():
    mid = datetime.now(timezone.utc) + timedelta(days=3)
    assert _ttl_days_from(mid) == 3   # 報價剩 3 天，token 跟著報價、不到上限


def test_short_quote_not_below_1_day():
    soon = datetime.now(timezone.utc) + timedelta(hours=6)
    assert _ttl_days_from(soon) == 1   # ceil(0.25)=1，未被上限影響


def test_expired_quote_min_1_day():
    past = datetime.now(timezone.utc) - timedelta(days=3)
    assert _ttl_days_from(past) == 1
