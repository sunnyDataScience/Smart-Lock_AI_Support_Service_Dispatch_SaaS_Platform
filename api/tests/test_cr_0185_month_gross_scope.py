"""CR-0185：師傅站 month_gross_est 的「本月」口徑（2026-07-27）。

**Bug**：`get_my_dashboard_summary` 的 pending 聚合欄原本**沒有任何日期條件**
（`completed_at IS NULL AND status IN (...)`），而 month_gross_est = 本月完工 + pending，
於是「本月毛額」把**全歷史**未完工工單都算進來 —— 線上實測本月 0 單仍顯示 NT$31,617，
與同一支 SQL 下一欄用 `date_trunc('month')` 的 month_total_orders 自相矛盾。

**修法**：pending 亦加月份窗，錨點 `COALESCE(scheduled_at, created_at)`
（已排程者以排程月為準——跨月承接的工作算在實際要做的那個月；未排程者退回建立月）。
同時移除 status 白名單中 'scheduled'/'en_route'/'arrived' 三個死值（API 層 enum，
work_orders.status 正典狀態機不含，永遠 match 不到）。

兩層驗證：①SQL 形狀（無 DB，防日期窗被拿掉）②真 DB 行為（跨月 pending 確實被排除）。
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest

import core.db as db_module
from services import technician_service as svc

_MARK = "cr0185-scope-test"


# ── ① SQL 形狀守線（無 DB 依賴）─────────────────────────────────────────
def _dashboard_sql() -> str:
    """從原始碼取出 dashboard summary 那支 SQL 的組合結果。"""
    src = (Path(__file__).resolve().parents[1] / "services" / "technician_service.py").read_text(
        encoding="utf-8"
    )
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute" and node.args
                and isinstance(node.args[0], ast.Constant)
                and "date_trunc('week'" in str(node.args[0].value)):
            return str(node.args[0].value)
    raise AssertionError("找不到 dashboard summary SQL")


def test_pending_column_is_month_scoped():
    """pending 聚合欄必須帶月份窗——這正是本 CR 修的 bug，回歸即失守。"""
    sql = _dashboard_sql()
    i = sql.find("completed_at IS NULL")
    assert i > 0, "找不到 pending 聚合欄"
    pending_col = sql[i:i + 260]
    assert "date_trunc('month'" in pending_col, (
        "pending 欄失去月份窗 → month_gross_est 會再度把全歷史未完工工單算進「本月毛額」\n"
        f"實際片段：{pending_col}"
    )
    assert "COALESCE(scheduled_at, created_at)" in pending_col, "月份窗錨點應為 COALESCE(scheduled_at, created_at)"


def test_pending_status_whitelist_has_no_dead_values():
    """'scheduled'/'en_route'/'arrived' 是 API 層 enum，DB 狀態機不含，不應出現在 SQL。"""
    sql = _dashboard_sql()
    i = sql.find("completed_at IS NULL")
    pending_col = sql[i:i + 260]
    for dead in ("'scheduled'", "'en_route'", "'arrived'"):
        assert dead not in pending_col, f"死條件 {dead} 又出現（work_orders.status 永不為此值）"


# ── ② 真 DB 行為（跨月 pending 必須被排除）──────────────────────────────
@pytest.fixture
async def _tech_with_orders():
    """建一名技師 + 三張未完工工單：上月建立未排程／本月排程／本月建立未排程。"""
    from core.db import _ensure_conn

    await _ensure_conn()
    tenant = "00000000-0000-0000-0000-000000000001"
    user_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    await db_module._conn.execute(
        "INSERT INTO users(id, tenant_id, display_name, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'technician', TRUE)",
        (user_id, tenant, _MARK),
    )
    await db_module._conn.execute(
        # name / phone 為 NOT NULL 無預設（technicians 僅此兩欄必填）
        "INSERT INTO technicians(id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'active')",
        (tech_id, tenant, user_id, _MARK, "0900000185"),
    )

    async def _wo(price, created_sql, scheduled_sql):
        await db_module._conn.execute(
            "INSERT INTO work_orders(id, tenant_id, technician_id, status, estimated_price, "
            "  customer_name, created_at, scheduled_at) "
            f"VALUES (gen_random_uuid(), %s::uuid, %s::uuid, 'in_progress', %s, %s, "
            f"  {created_sql}, {scheduled_sql})",
            (tenant, tech_id, price, _MARK),
        )

    _LAST_MONTH = "date_trunc('month', CURRENT_DATE) - interval '20 days'"
    _THIS_MONTH = "date_trunc('month', CURRENT_DATE) + interval '1 day'"

    # (a) 上月建立、未排程 → 不該計入本月
    await _wo(1000, _LAST_MONTH, "NULL")
    # (b) 上月建立、但排在本月 → 該計入本月
    await _wo(200, _LAST_MONTH, "date_trunc('month', CURRENT_DATE) + interval '2 days'")
    # (c) 本月建立、未排程 → 該計入本月
    await _wo(30, _THIS_MONTH, "NULL")

    yield {"tenant": tenant, "user_id": user_id, "tech_id": tech_id}

    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute("DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest.mark.asyncio
async def test_cross_month_pending_excluded_from_month_gross(_tech_with_orders):
    """上月建立且未排程的未完工單，不得計入本月毛額；本月排程/建立者則計入。"""
    ctx = _tech_with_orders
    got = await svc.get_my_dashboard_summary(
        tenant_id=ctx["tenant"], user_id=ctx["user_id"])

    # 期望 = (b)200 + (c)30 = 230；(a)1000 為上月遺留、未排本月 → 排除
    assert got["month_pending_est"] == pytest.approx(230.0), (
        f"pending 口徑錯誤：得 {got['month_pending_est']}，"
        "應只含本月排程(200)＋本月建立(30)，不含上月未排程(1000)"
    )
    # 本月無完工 → 毛額即 pending
    assert got["month_gross_est"] == pytest.approx(got["month_pending_est"]), (
        "本月無完工時 month_gross_est 應等於 month_pending_est"
    )
    assert got["month_gross_est"] < 1000, "上月遺留工單仍被算進本月毛額（本 CR 要修的正是這個）"
