"""CR-0038 桶4 公單收尾測試（BR-M08-02 scope tier 分級閘 + Q063 48h 自動結案）。

component（真 DB，需 migration 053 config）：
- _classify_scope_tier：minor/standard/major + major_pct 覆寫（門檻讀 config）
- auto_confirm_stale_completed：逾期 completed → confirmed/closed；排除過近/high_risk_hold/open exception
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import work_order_service as svc

pytestmark = pytest.mark.component


# ── scope tier 分級（BR-M08-02）──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scope_tier_minor():
    assert await db_module._ensure_conn()
    r = await svc._classify_scope_tier(10000, 10300)  # delta 300 ≤500, pct 0.03
    assert r["tier"] == "minor"
    assert r["requires_supervisor"] is False


@pytest.mark.asyncio
async def test_scope_tier_standard():
    assert await db_module._ensure_conn()
    r = await svc._classify_scope_tier(10000, 11500)  # delta 1500 (501-2000), pct 0.15
    assert r["tier"] == "standard"
    assert r["requires_supervisor"] is False


@pytest.mark.asyncio
async def test_scope_tier_major_by_amount():
    assert await db_module._ensure_conn()
    r = await svc._classify_scope_tier(100000, 103000)  # delta 3000 >2000, pct 0.03
    assert r["tier"] == "major"
    assert r["requires_supervisor"] is True


@pytest.mark.asyncio
async def test_scope_tier_major_by_pct():
    assert await db_module._ensure_conn()
    r = await svc._classify_scope_tier(1000, 1600)  # delta 600 (standard 金額) 但 pct 0.6 ≥0.5
    assert r["tier"] == "major"  # 比例覆寫金額分級
    assert r["requires_supervisor"] is True


# ── 48h 自動結案（Q063）─────────────────────────────────────────────────────
async def _insert_completed_wo(wo_id: str, *, hours_ago: int, hold: bool = False) -> None:
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, completed_at, high_risk_hold) "
        "VALUES (%s::uuid, 'completed', '測試地址 1 號', NOW() - make_interval(hours => %s), %s)",
        (wo_id, hours_ago, hold),
    )


async def _status(wo_id: str) -> tuple:
    cur = await db_module._conn.execute(
        "SELECT status, completion_status FROM work_orders WHERE id = %s::uuid", (wo_id,)
    )
    return await cur.fetchone()


@pytest.mark.asyncio
async def test_auto_confirm_stale_completed():
    assert await db_module._ensure_conn()
    old, recent, held = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await _insert_completed_wo(old, hours_ago=49)
    await _insert_completed_wo(recent, hours_ago=1)
    await _insert_completed_wo(held, hours_ago=49, hold=True)
    try:
        n = await svc.auto_confirm_stale_completed()
        assert n >= 1
        assert (await _status(old)) == ("confirmed", "closed")     # 逾期 → 自動結案
        assert (await _status(recent))[0] == "completed"           # 過近 → 不動
        assert (await _status(held))[0] == "completed"             # high_risk_hold → 排除
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE id IN (%s::uuid, %s::uuid, %s::uuid)",
            (old, recent, held),
        )
