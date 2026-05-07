"""Workday SLA helper — Q4=C 拍板：工作日 + 國定假日跳過。

PM 拍板（Q4=C）：月結爭議 SLA 7 日改為「工作日」計算，且需跳過台灣國定假日。
本模組提供唯一可信的工作日計算入口，避免散落的 ``timedelta(days=N)`` 自然日邏輯。

設計原則：
- 唯一資料來源：``holidays.country_holidays('TW')`` — 涵蓋元旦、春節、清明、端午、
  中秋、國慶、勞動節等法定假日，由套件作者維護年度更新。
- 邊界語意：``add_workdays`` 不把 ``start`` 當天計入；從次日開始往後找 N 個工作日。
  例：start=週一，add_workdays(start, 1) → 週二（不論週一是不是工作日）。
- 純函式：所有 helper 皆無副作用，可安全於並行情境呼叫。
- 性能：對單筆 SLA 計算（N <= 30）用樸素迴圈即可；如有批次需求再考慮快取。

呼叫點（截至引入時）：
- 尚未有 production 程式碼計算 ``disputes.sla_deadline``（DB 欄位存在但寫入點未實作）。
- 引入此 helper 為 F-013（月結爭議 7 工作日 SLA）做準備；未來 settlement / dispute
  service 寫入 ``sla_deadline`` 時必須走此 helper。
- TODO(F-013): api/services/dispute_service.py 在實作 ``submit_dispute`` /
  ``create_settlement_dispute`` 時，呼叫 ``workday_sla_deadline(filed_at, 7)``
  取代 ``filed_at + timedelta(days=7)``。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import holidays

# 模組級單例：holidays 套件本身有內部快取，這裡只是顯式宣告 country=TW
TW_HOLIDAYS: holidays.HolidayBase = holidays.country_holidays("TW")


def is_workday(d: date) -> bool:
    """週一至週五 + 非台灣國定假日 = 工作日。

    Args:
        d: 要檢查的日期（``datetime.date``；如傳 ``datetime`` 會自動取 ``.date()``）。

    Returns:
        True iff d 是週一~週五且不在台灣國定假日清單。
    """
    # 容錯：若呼叫端傳了 datetime 而非 date
    if isinstance(d, datetime):
        d = d.date()
    return d.weekday() < 5 and d not in TW_HOLIDAYS


def add_workdays(start: datetime, n_workdays: int) -> datetime:
    """從 start 開始算 n 個工作日後的日期/時間。

    語意：start 當天不計入；從次日起逐日往後找，每遇一個工作日就 -1，
    直到 n_workdays 歸零為止。時、分、秒、tzinfo 保留 start 的值。

    Args:
        start: 起算時間（含時分秒）。
        n_workdays: 要往後推進的工作日數量；必須 >= 0。

    Returns:
        推進 n 個工作日後的 datetime；n=0 時直接回 start（不變）。

    Raises:
        ValueError: 若 n_workdays 為負數。
    """
    if n_workdays < 0:
        raise ValueError(f"n_workdays must be >= 0, got {n_workdays}")
    current = start
    remaining = n_workdays
    while remaining > 0:
        current = current + timedelta(days=1)
        if is_workday(current.date()):
            remaining -= 1
    return current


def workday_sla_deadline(start: datetime, sla_workdays: int) -> datetime:
    """SLA 截止時間 = start + N 工作日（語意 wrapper）。

    與 ``add_workdays`` 等價，存在的目的是讓呼叫端意圖更明確（這是 SLA 計算，
    不是任意工作日推進）。F-013 的所有 SLA deadline 計算都應該走這個函式。

    Args:
        start: SLA 起算時間（通常是 ``filed_at`` 或 ``created_at``）。
        sla_workdays: SLA 規範的工作日數（Q4=C：月結爭議為 7）。

    Returns:
        SLA 到期 datetime。
    """
    return add_workdays(start, sla_workdays)


def workdays_between(start: date, end: date) -> int:
    """計算兩日期間的工作日數（不含 start，含 end）。

    用途：技師工時統計、SLA 違約日數計算等。
    語意：(start, end] — 從 start 隔天開始數，數到 end 為止。

    Args:
        start: 起始日（不計入）。
        end: 結束日（計入）。

    Returns:
        工作日數量；若 end < start，回傳負數（對稱性）。
    """
    if end < start:
        return -workdays_between(end, start)
    count = 0
    current = start
    while current < end:
        current = current + timedelta(days=1)
        if is_workday(current):
            count += 1
    return count
