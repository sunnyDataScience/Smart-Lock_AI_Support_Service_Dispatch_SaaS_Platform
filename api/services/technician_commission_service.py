"""Technician Commission Service — CR-0106 師傅佣金月結（固定工資制）。

承載師傅詳情頁右欄「佣金摘要」的真實資料（取代前端寫死的抽成制 mock）。

**模型來源**：`20260617資料/…PhaseII_FinanceSettlement…xlsx`（業主 2026-06-27 核准 Q-09 草稿費率）。
真實為「固定工資制」非 mock 的抽成制：
  - 每張完工工單的服務明細（quote_line_items.service_code）× 該技師等級的 base_payout（payout_rule）。
  - 月結工資 = Σ(base_payout × quantity)；月底彙總為 AP Ledger 應付。

**資料鏈**：work_orders（completed）→ quote_line_items(service_code) → technician_payout_rule(service_code, level_id)。

**本階段範圍 / 誠實限制**：
  - 夜間/急件加成（payout_rule 有欄）**不自動套用** —— 觸發條件 Q-03（急件）/ Q-04（夜間時段）
    仍「待回答」，自動判定會腦補，故 surcharge=0，待業主定義後再開。
  - 扣項（車馬費/平台費/未繳回現金/爭議暫扣，AP Ledger）無結構化來源 → 暫 0，待月結模組。
  - 等級映射：technicians.level S/A/B/C → payout LV-A/B/C（來源「19 鎖匠等級」僅 A/B/C，無 S）；
    S 暫映 LV-A（最高已定義級）—— 待業主補 S 級費率。
  - 無已完工工單 → 回空（gross 0）；有真實工單流入即自動填值（同認證矩陣「真但空」）。
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date

from psycopg import errors as pg_errors

import core.db as db_module
from core.db import _ensure_conn, require_tech_conn
from core.errors import ApiError

logger = logging.getLogger("api.technician_commission_service")

# technicians.level（S/A/B/C）→ payout_rule.level_id（LV-A/B/C）。
# 來源「19 鎖匠等級」僅定義 A/B/C；S 無對應費率 → 暫映最高級 LV-A（CR-0106 §限制，待業主補 S 級）。
_LEVEL_MAP = {"S": "LV-A", "A": "LV-A", "B": "LV-B", "C": "LV-C"}

_COMPLETED_STATUSES = ("completed", "closed")


def _month_range(year: int, month: int) -> tuple[date, date]:
    if not (1 <= month <= 12):
        raise ApiError("VALIDATION_ERROR", "month 必須 1..12", 422)
    start = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    # 區間 [start, next_month_start)
    end = date(year, month, last_day)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, nxt


async def compute_monthly_commission(
    *, tenant_id: str, technician_id: str, year: int, month: int
) -> dict:
    """計算某技師某月的佣金摘要（固定工資制）。

    回傳：等級、本月工資 gross、服務明細 lines、扣項 deductions（暫 0）、應付 net、
    完工單數、未對到費率筆數（unmapped）、誠實註記。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 技師存在 + 取等級（tenant 隔離）
    cur = await db_module._conn.execute(
        "SELECT level FROM technicians WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Technician not found", 404)
    level = (row[0] or "C").upper()
    level_id = _LEVEL_MAP.get(level, "LV-C")

    start, nxt = _month_range(year, month)

    # 完工工單數（distinct）
    cnt = await (await db_module._conn.execute(
        "SELECT COUNT(*) FROM work_orders "
        "WHERE tenant_id = %s::uuid AND technician_id = %s::uuid "
        "  AND completion_status = ANY(%s) "
        "  AND completed_at >= %s AND completed_at < %s",
        (tenant_id, technician_id, list(_COMPLETED_STATUSES), start, nxt),
    )).fetchone()
    completed_orders = int(cnt[0] or 0)

    # 服務明細 × 費率（LEFT JOIN：未對到費率的 service 仍列出但 payout=NULL → unmapped）
    cur = await db_module._conn.execute(
        "SELECT qli.service_code, "
        "       COALESCE(pr.service_name, qli.item_name) AS name, "
        "       SUM(qli.quantity)::int AS qty, "
        "       pr.base_payout "
        "FROM work_orders wo "
        "JOIN quote_line_items qli ON qli.work_order_id = wo.id "
        "LEFT JOIN technician_payout_rule pr "
        "       ON pr.service_code = qli.service_code AND pr.level_id = %s "
        "WHERE wo.tenant_id = %s::uuid AND wo.technician_id = %s::uuid "
        "  AND wo.completion_status = ANY(%s) "
        "  AND wo.completed_at >= %s AND wo.completed_at < %s "
        "  AND qli.service_code IS NOT NULL "
        "GROUP BY qli.service_code, name, pr.base_payout "
        "ORDER BY qli.service_code",
        (level_id, tenant_id, technician_id, list(_COMPLETED_STATUSES), start, nxt),
    )
    rows = await cur.fetchall()

    lines: list[dict] = []
    gross = 0.0
    unmapped = 0
    for r in rows:
        service_code, name, qty, base_payout = r[0], r[1], int(r[2] or 0), r[3]
        mapped = base_payout is not None
        unit = float(base_payout) if mapped else 0.0
        line_total = round(unit * qty, 2)
        if not mapped:
            unmapped += 1
        gross += line_total
        lines.append({
            "service_code": service_code,
            "service_name": name,
            "quantity": qty,
            "unit_payout": unit,
            "line_total": line_total,
            "mapped": mapped,
        })
    gross = round(gross, 2)

    # 扣項：AP Ledger 結構（暫 0，待月結模組接結構化來源）
    deductions = {
        "travel_fee": 0.0,
        "platform_fee": 0.0,
        "uncollected_cash": 0.0,
        "dispute_hold": 0.0,
    }
    deduction_total = round(sum(deductions.values()), 2)
    net = round(gross - deduction_total, 2)

    return {
        "year": year,
        "month": month,
        "level": level,
        "level_id": level_id,
        "completed_orders": completed_orders,
        "gross_amount": gross,
        "deductions": deductions,
        "deduction_total": deduction_total,
        "net_amount": net,
        "currency": "TWD",
        "lines": lines,
        "unmapped_count": unmapped,
        # 誠實註記（前端可顯示）：加成/扣項未開、費率來源
        "notes": {
            "surcharge_applied": False,  # 夜間/急件加成待 Q-03/Q-04
            "deductions_wired": False,   # 扣項待月結模組
            "rate_source": "technician_payout_rule（業主 2026-06-27 核准）",
        },
    }


async def list_my_commission_statements(
    *, tenant_id: str, user_id: str, limit: int = 24
) -> dict:
    """技師本人佣金對帳單（UAT P2-5：tech surface 缺此端點 → 對帳單頁 404）。

    來源 = technician_commission_projection（CR-0166 R4 / ADR-017 技師視角
    跨品牌 CQRS 投影，commission.accrued 事件物化；雙庫模式讀技師權威庫，
    單庫 fallback 主庫）。依月彙總（period=YYYY-MM），每期回
    {period, gross_amount, commission_amount, status}。

    誠實限制：
      - 投影欄位最小化（ADR-017 §投影隱私）只帶佣金 accrued 金額，無工單毛額
        → gross_amount 以當期佣金累計代替（＝commission_amount），待事件補帶毛額。
      - 投影無對帳單狀態機 → status 一律 'accrued'（月結中），待月結模組。
      - 無資料（含投影表尚未建立——consumer 未啟動過的部署）→ 空 items 200，不 404。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # users.id → technicians.id（投影以 technician_id 關聯；查無技師列＝尚無佣金）
    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE user_id = %s::uuid AND tenant_id = %s::uuid",
        (user_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        return {"items": []}
    technician_id = str(row[0])

    conn = await require_tech_conn()
    try:
        cur = await conn.execute(
            "SELECT to_char(date_trunc('month', COALESCE(accrued_at, created_at)), 'YYYY-MM') "
            "         AS period, "
            "       SUM(amount), COUNT(*), MAX(currency) "
            "FROM technician_commission_projection "
            "WHERE technician_id = %s::uuid "
            "GROUP BY period ORDER BY period DESC LIMIT %s",
            (technician_id, limit),
        )
        rows = await cur.fetchall()
    except pg_errors.UndefinedTable:
        # 投影表由 event_consumer.ensure_schema() 建（opt-in）；未建＝尚無佣金
        # 事件流入 → fail-soft 回空清單（UAT P2-5：不可 404/500）
        logger.warning(
            "technician_commission_projection 不存在（consumer 未啟動過）→ 回空對帳單"
        )
        return {"items": []}

    items = [{
        "period": r[0],
        # 投影未帶工單毛額 → gross 以佣金累計代替（見 docstring 誠實限制）
        "gross_amount": f"{float(r[1] or 0):.2f}",
        "commission_amount": f"{float(r[1] or 0):.2f}",
        "status": "accrued",
        "items_count": int(r[2] or 0),
        "currency": r[3] or "TWD",
    } for r in rows]
    return {"items": items}
