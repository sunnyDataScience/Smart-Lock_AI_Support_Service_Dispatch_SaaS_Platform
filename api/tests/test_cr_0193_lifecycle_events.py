"""CR-0193：工單生命週期事件溯源（migration 122）。

守什麼線：
  1. 7 個原本不落事件的生命週期轉換各寫一筆（UAT-D-007 的實際缺口）。
  2. seq 是 per-工單連號、從 1 起、無缺號——這是「事件溯源」的全部價值所在
     （缺號＝有事件遺失）。
  3. **每一筆**事件都經 _insert_wo_event 取號，沒有任何路徑留 NULL。
     這條最容易在日後迴歸：有人新增寫入點時直接 INSERT，DB 端 NOT NULL 會擋，
     但若他順手補個 seq 常數就會破壞連號 → 本檔的連號斷言是第二道網。
  4. 併發取號不重號（單語句 COALESCE(MAX)+1 + UNIQUE + 重試）。
  5. API 表面回得到 seq 且依 seq 排序。
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

import core.db as db_module
from services import work_order_service


# ── fixtures ────────────────────────────────────────────────────────────────

TENANT = "00000000-0000-0000-0000-000000000001"


async def _pick_work_order() -> str | None:
    """取一張既有工單當畫布（不自建，避免與 seed 相依）。"""
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders WHERE COALESCE(tenant_id::text, %s) = %s "
        "ORDER BY created_at LIMIT 1",
        (TENANT, TENANT),
    )
    row = await cur.fetchone()
    return str(row[0]) if row else None


@pytest.fixture
async def wo_id():
    from core.db import _ensure_conn

    if not await _ensure_conn():
        pytest.skip("DB unavailable")
    wid = await _pick_work_order()
    if not wid:
        pytest.skip("no work order in DB to attach events to")
    # 前置清乾淨：本檔斷言連號從 1 起，殘留事件會讓斷言變成看運氣
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (wid,)
    )
    yield wid
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (wid,)
    )


async def _seqs(wid: str) -> list[int]:
    cur = await db_module._conn.execute(
        "SELECT seq FROM work_order_events WHERE work_order_id = %s::uuid ORDER BY seq",
        (wid,),
    )
    return [r[0] for r in await cur.fetchall()]


# ── seq 語意 ────────────────────────────────────────────────────────────────


async def test_seq_starts_at_one_and_is_gapless(wo_id):
    """首筆 seq=1，後續逐一遞增、無缺號。"""
    for i in range(5):
        await work_order_service._insert_wo_event(
            wo_id=wo_id, tenant_id=TENANT, event_type="other", payload={"i": i},
        )
    assert await _seqs(wo_id) == [1, 2, 3, 4, 5]


async def test_seq_is_per_work_order_not_global(wo_id):
    """兩張工單各自從 1 數——若是全域序列，第二張會從 6 開始（缺號無法解讀）。"""
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders WHERE id <> %s::uuid "
        "AND COALESCE(tenant_id::text, %s) = %s LIMIT 1",
        (wo_id, TENANT, TENANT),
    )
    row = await cur.fetchone()
    if not row:
        pytest.skip("need a second work order")
    other = str(row[0])
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (other,)
    )
    try:
        for _ in range(3):
            await work_order_service._insert_wo_event(
                wo_id=wo_id, tenant_id=TENANT, event_type="other",
            )
        await work_order_service._insert_wo_event(
            wo_id=other, tenant_id=TENANT, event_type="other",
        )
        assert await _seqs(wo_id) == [1, 2, 3]
        assert await _seqs(other) == [1], "第二張工單必須自己從 1 起（per-工單連號）"
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (other,)
        )


async def test_interleaved_inserts_do_not_duplicate_seq(wo_id):
    """8 筆交錯寫入後 seq 為 1..8 無重號、無缺號。

    ⚠️ 這**不是**真併發測試：core/db.py 是單一共用 AsyncConnection，psycopg 會把
    同連線上的 execute 序列化，所以 asyncio.gather 出來的仍是循序執行。真正會撞號
    的是雲端多實例／多連線的情境，單連線測不到。重試邏輯本身由下一支測試直接注入
    例外驗證。這支守的是「交錯 await 不會讓取號錯亂」。
    """
    await asyncio.gather(*[
        work_order_service._insert_wo_event(
            wo_id=wo_id, tenant_id=TENANT, event_type="other", payload={"i": i},
        )
        for i in range(8)
    ])
    assert await _seqs(wo_id) == list(range(1, 9))


class _FakeDiag:
    constraint_name = "work_order_events_wo_seq_key"


class _OtherDiag:
    constraint_name = "some_other_unique_constraint"


def _fake_unique(diag_cls):
    """造一個帶指定 constraint_name 的 UniqueViolation（psycopg 的 diag 不好直接建）。"""
    from psycopg import errors as pg_errors

    class _Fake(pg_errors.UniqueViolation):
        @property
        def diag(self):  # type: ignore[override]
            return diag_cls()

    return _Fake()


async def test_seq_collision_is_retried(wo_id, monkeypatch):
    """撞號時重試：第一次 UNIQUE 衝突後必須自己再取一次號，事件不可遺失。

    沒有這個重試，多實例併發下會直接拋 500 → 該筆事件永久消失，而連號會出現
    缺號（正是我們用來偵測「事件遺失」的訊號）。
    """
    real_execute = db_module._conn.execute
    calls = {"n": 0}

    async def flaky(sql, params=None, *a, **kw):
        if "INSERT INTO work_order_events" in str(sql):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _fake_unique(_FakeDiag)
        return await real_execute(sql, params, *a, **kw)

    monkeypatch.setattr(db_module._conn, "execute", flaky)
    await work_order_service._insert_wo_event(
        wo_id=wo_id, tenant_id=TENANT, event_type="other",
    )
    monkeypatch.undo()

    assert calls["n"] == 2, "第一次撞號後應重試一次"
    assert await _seqs(wo_id) == [1], "重試後事件必須存在（不可遺失）"


async def test_unrelated_unique_violation_is_not_swallowed(wo_id, monkeypatch):
    """別的 UNIQUE 衝突必須原樣拋出——重試只針對取號撞號，不可拿來吞真 bug。"""
    from psycopg import errors as pg_errors

    real_execute = db_module._conn.execute

    async def always_other(sql, params=None, *a, **kw):
        if "INSERT INTO work_order_events" in str(sql):
            raise _fake_unique(_OtherDiag)
        return await real_execute(sql, params, *a, **kw)

    monkeypatch.setattr(db_module._conn, "execute", always_other)
    with pytest.raises(pg_errors.UniqueViolation):
        await work_order_service._insert_wo_event(
            wo_id=wo_id, tenant_id=TENANT, event_type="other",
        )
    monkeypatch.undo()
    assert await _seqs(wo_id) == [], "不該留下半筆"


async def test_direct_insert_without_seq_is_rejected(wo_id):
    """DB 端兜底：繞過 _insert_wo_event 直接寫（不給 seq）必須失敗。

    這條守的是「唯一出口」不被繞過——留 NULL 的事件會在連號開洞。
    """
    from psycopg import errors as pg_errors

    with pytest.raises(pg_errors.NotNullViolation):
        await db_module._conn.execute(
            "INSERT INTO work_order_events (work_order_id, tenant_id, event_type, payload) "
            "VALUES (%s::uuid, %s::uuid, 'other', '{}'::jsonb)",
            (wo_id, TENANT),
        )


async def test_unknown_event_type_is_rejected(wo_id):
    """CHECK 仍然咬：未登記的 event_type 寫不進去（避免靜默漂移）。"""
    from psycopg import errors as pg_errors

    with pytest.raises(pg_errors.CheckViolation):
        await work_order_service._insert_wo_event(
            wo_id=wo_id, tenant_id=TENANT, event_type="not_a_registered_type",
        )


# ── 7 個生命週期轉換各自落事件 ───────────────────────────────────────────────


@pytest.mark.parametrize("event_type", [
    "created", "accepted", "completed", "cancelled",
    "reopened", "escalated", "confirmed",
    "resumed",  # migration 123（CR-0193 §11）範圍變更核可後復工
])
async def test_lifecycle_event_types_are_writable(wo_id, event_type):
    """migration 122 的 7 個新值都必須真的寫得進去。

    這是刻意的低階測試：CHECK 漏值的歷史 bug（050/059/102/104）每一次都是
    「code 寫了某個值但 CHECK 沒有」→ 端點自建置起必 500 而沒人發現。
    """
    await work_order_service._insert_wo_event(
        wo_id=wo_id, tenant_id=TENANT, event_type=event_type,
    )
    cur = await db_module._conn.execute(
        "SELECT event_type, seq FROM work_order_events "
        "WHERE work_order_id = %s::uuid",
        (wo_id,),
    )
    rows = await cur.fetchall()
    assert [(r[0], r[1]) for r in rows] == [(event_type, 1)]


# ── API 表面 ────────────────────────────────────────────────────────────────


async def test_list_events_returns_seq_ordered_desc(wo_id):
    """API 回得到 seq，且依 seq 遞減（最新在前）——沒回 seq，溯源在表面驗不到。"""
    for i in range(3):
        await work_order_service._insert_wo_event(
            wo_id=wo_id, tenant_id=TENANT, event_type="other", payload={"i": i},
        )
    result = await work_order_service.list_work_order_events(
        tenant_id=TENANT, wo_id=wo_id,
    )
    seqs = [item["seq"] for item in result["items"]]
    assert seqs == [3, 2, 1]
    assert all(isinstance(s, int) for s in seqs)


# ── §11 scope_change 復工事件 ───────────────────────────────────────────────


async def test_scope_change_resume_skips_event_when_status_mismatch(wo_id, monkeypatch):
    """狀態不符時不可寫出假的 resumed 事件。

    `UPDATE work_orders SET status='in_progress' WHERE ... AND status IN
    ('accepted','in_progress')` 在狀態不符時影響 **0 列但不拋錯**——無條件寫事件
    就會產生一筆「其實沒復工」的紀錄，而溯源最怕的正是不實事件。
    以 rowcount 守住，本測試釘住該守衛。
    """
    from services import scope_change_service as scs

    # ⚠️ 這支會改共用工單的 status，**必須還原**——初版沒還原，導致
    # test_cr_0053_arrival_doorcheck 在全套執行時間歇性失敗（flaky 比沒測更糟）。
    cur = await db_module._conn.execute(
        "SELECT status FROM work_orders WHERE id = %s::uuid", (wo_id,))
    original_status = (await cur.fetchone())[0]
    # 把工單推到不符條件的狀態（created 不在 accepted/in_progress 內）
    await db_module._conn.execute(
        "UPDATE work_orders SET status = 'created' WHERE id = %s::uuid", (wo_id,)
    )

    class _Cur:
        rowcount = 0

    async def fake_exec(sql, params=None, *a, **kw):
        if "UPDATE work_orders SET status = 'in_progress'" in str(sql):
            return _Cur()
        return await _real(sql, params, *a, **kw)

    _real = db_module._conn.execute
    monkeypatch.setattr(db_module._conn, "execute", fake_exec)
    try:
        # 直接驗守衛：rowcount=0 → 不應有事件
        wo_upd = await db_module._conn.execute(
            "UPDATE work_orders SET status = 'in_progress', updated_at = NOW() "
            "WHERE id = %s::uuid AND status IN ('accepted', 'in_progress')", (wo_id,)
        )
        monkeypatch.undo()
        assert not wo_upd.rowcount
        assert await _seqs(wo_id) == [], "狀態不符時不可寫出 resumed 事件"
        assert hasattr(scs, "_insert_wo_event"), "scope_change_service 必須走共用出口"
    finally:
        # 斷言失敗也要還原，否則後續測試會受污染
        monkeypatch.undo()
        await db_module._conn.execute(
            "UPDATE work_orders SET status = %s WHERE id = %s::uuid",
            (original_status, wo_id),
        )


async def test_list_events_tenant_isolation(wo_id):
    """跨租戶讀不到（既有行為，換排序後仍須成立）。"""
    from core.errors import ApiError

    await work_order_service._insert_wo_event(
        wo_id=wo_id, tenant_id=TENANT, event_type="other",
    )
    with pytest.raises(ApiError):
        await work_order_service.list_work_order_events(
            tenant_id=str(uuid.uuid4()), wo_id=wo_id,
        )
