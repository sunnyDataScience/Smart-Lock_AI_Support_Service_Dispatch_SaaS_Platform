"""Unit tests for ``core.workday`` (Q4=C 工作日 SLA helper).

涵蓋 4 個 helper：
- ``is_workday`` — 週末 / 國定假日 / 普通工作日的識別
- ``add_workdays`` — 跨週末、跨國定假日（春節）、邊界 n=0 / 負數
- ``workday_sla_deadline`` — F-013 月結爭議 7 工作日 SLA 計算
- ``workdays_between`` — 完整週、跨假日、對稱性（end < start）

選定的 anchor 日期（取自 holidays 套件 v0.96 的 TW 2026 年資料）：
- 2026-01-01 (Thu) — 元旦
- 2026-02-16 ~ 2026-02-20 — 春節連假（5 天，全部撞工作日）
- 2026-02-13 (Fri) — 春節前最後一個工作日
- 2026-05-04 (Mon) ~ 2026-05-08 (Fri) — 乾淨的一週（無假日）
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from core.workday import (
    add_workdays,
    is_workday,
    workday_sla_deadline,
    workdays_between,
)

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────
# is_workday
# ─────────────────────────────────────────────


def test_is_workday_ordinary_weekday_is_true():
    # 2026-05-04 是週一且非假日
    assert is_workday(date(2026, 5, 4)) is True


def test_is_workday_saturday_is_false():
    # 2026-05-09 是週六
    assert is_workday(date(2026, 5, 9)) is False


def test_is_workday_sunday_is_false():
    # 2026-05-10 是週日
    assert is_workday(date(2026, 5, 10)) is False


def test_is_workday_lunar_new_year_is_false():
    # 2026-02-17 是春節（週二）— 撞工作日但因國定假日而非工作日
    assert is_workday(date(2026, 2, 17)) is False


def test_is_workday_new_year_day_is_false():
    # 2026-01-01 是元旦（週四）
    assert is_workday(date(2026, 1, 1)) is False


def test_is_workday_accepts_datetime():
    # 容錯：datetime 物件應自動轉 date
    assert is_workday(datetime(2026, 5, 4, 10, 30)) is True
    assert is_workday(datetime(2026, 5, 9, 10, 30)) is False


# ─────────────────────────────────────────────
# add_workdays — 基礎與跨週末
# ─────────────────────────────────────────────


def test_add_workdays_zero_returns_same():
    start = datetime(2026, 5, 4, 9, 0)
    assert add_workdays(start, 0) == start


def test_add_workdays_one_within_same_week():
    # 週一 +1 工作日 → 週二
    start = datetime(2026, 5, 4, 9, 0)  # Mon
    assert add_workdays(start, 1) == datetime(2026, 5, 5, 9, 0)


def test_add_workdays_crosses_weekend():
    # 週五 +1 工作日 → 下週一（跳過週六、日）
    start = datetime(2026, 5, 8, 9, 0)  # Fri
    assert add_workdays(start, 1) == datetime(2026, 5, 11, 9, 0)


def test_add_workdays_full_week_is_seven_natural_days():
    # 週一 +5 工作日 → 下週一（跨一個週末）
    start = datetime(2026, 5, 4, 9, 0)  # Mon
    assert add_workdays(start, 5) == datetime(2026, 5, 11, 9, 0)


def test_add_workdays_preserves_time_component():
    # 時、分、秒不變
    start = datetime(2026, 5, 4, 14, 30, 45)
    result = add_workdays(start, 3)
    assert result.hour == 14
    assert result.minute == 30
    assert result.second == 45


# ─────────────────────────────────────────────
# add_workdays — 跨春節
# ─────────────────────────────────────────────


def test_add_workdays_crosses_lunar_new_year():
    # 2026-02-13 (Fri, 春節前最後一個工作日) +1 工作日
    # 跳過 02-14/15 (週末) + 02-16~20 (春節 5 天) + 02-21/22 (週末)
    # → 落在 2026-02-23 (Mon)
    start = datetime(2026, 2, 13, 9, 0)
    assert add_workdays(start, 1) == datetime(2026, 2, 23, 9, 0)


# ─────────────────────────────────────────────
# add_workdays — 邊界
# ─────────────────────────────────────────────


def test_add_workdays_negative_raises():
    with pytest.raises(ValueError, match="must be >= 0"):
        add_workdays(datetime(2026, 5, 4, 9, 0), -1)


# ─────────────────────────────────────────────
# workday_sla_deadline (F-013 月結爭議 7 工作日)
# ─────────────────────────────────────────────


def test_sla_deadline_seven_workdays_from_clean_monday():
    # 週一起算 +7 工作日 → 跨一個完整週末，落在第二週的週三
    # Mon(0) → Tue(1) Wed(2) Thu(3) Fri(4) Sat/Sun → Mon(5) Tue(6) Wed(7)
    start = datetime(2026, 5, 4, 9, 0)
    deadline = workday_sla_deadline(start, 7)
    assert deadline == datetime(2026, 5, 13, 9, 0)


def test_sla_deadline_seven_workdays_crosses_holiday():
    # 起算於春節前 2026-02-13 (Fri)，+7 工作日須跨完整春節週
    # +1 → 02-23 Mon, +2 → 02-24 Tue, +3 → 02-25 Wed, +4 → 02-26 Thu,
    # +5 → 03-02 Mon (因 02-27 為和平紀念日 observed, 02-28~03-01 週末)
    # +6 → 03-03 Tue, +7 → 03-04 Wed
    start = datetime(2026, 2, 13, 9, 0)
    deadline = workday_sla_deadline(start, 7)
    assert deadline == datetime(2026, 3, 4, 9, 0)


def test_sla_deadline_is_alias_of_add_workdays():
    # 兩者語意等價，僅命名不同（語意 wrapper）
    start = datetime(2026, 5, 4, 9, 0)
    assert workday_sla_deadline(start, 7) == add_workdays(start, 7)


# ─────────────────────────────────────────────
# workdays_between
# ─────────────────────────────────────────────


def test_workdays_between_full_week_is_five():
    # 週一到下週一 = 5 工作日（不含 start，含 end；end 是下週一也是工作日）
    assert workdays_between(date(2026, 5, 4), date(2026, 5, 11)) == 5


def test_workdays_between_same_day_is_zero():
    assert workdays_between(date(2026, 5, 4), date(2026, 5, 4)) == 0


def test_workdays_between_skips_lunar_new_year():
    # 2026-02-13 (Fri) → 2026-02-23 (Mon)：自然日 10 天，工作日只有 1 天（02-23）
    assert workdays_between(date(2026, 2, 13), date(2026, 2, 23)) == 1


def test_workdays_between_symmetric_when_reversed():
    # end < start 時回傳負數
    forward = workdays_between(date(2026, 5, 4), date(2026, 5, 11))
    backward = workdays_between(date(2026, 5, 11), date(2026, 5, 4))
    assert backward == -forward
