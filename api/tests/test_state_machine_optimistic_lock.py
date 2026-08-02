"""狀態機 transition 的樂觀鎖（CR-0199 方案 A，2026-08-02）。

**問題**：所有 transition 都是「SELECT status 檢查 → UPDATE」兩個獨立語句，
而本專案的 DB 連線是 **autocommit、無交易**。`work_order_service.py:607` 的既有
註解已記載這件事（UAT R3-6）：

> autocommit 下步驟 1 的 FOR UPDATE 鎖不跨語句

更糟的是 `_fetch_status_for_update()` 這個名字**謊報語意**——它的 SQL 裡根本
沒有 `FOR UPDATE`，只是「讀 status + 驗 tenant，找不到就 404」。後續開發者看到
`_for_update` 會以為有列鎖保護，因而放心做 check-then-act。

**失效路徑**：兩個並發的**異型** transition 會雙雙通過各自的狀態守衛，
後寫的覆蓋先寫的。例如技師拒單與小編改派撞在一起，reject 的 UPDATE 後執行，
把已改派給 B 的單打回 created 池，技師 B 的 app 上單子憑空消失。

**修法（方案 A）**：UPDATE 的 WHERE 追加 `AND status = <剛才讀到的那個>`，
`rowcount == 0` 就拋 409 STATE_CONFLICT。與 autocommit 相容，不需交易與列鎖。

---

## 為什麼不用真的並發來測

真並發需要兩條獨立連線且時序不可控，在 CI 上會 flaky。本檔改用**精確競態窗口
注入**：monkeypatch `_fetch_status_for_update`，讓它回傳**過期的** status 之前，
先偷偷把 DB 的實際狀態改掉。這精確重現了 check-then-act 的競態窗口，而且每次
都必然發生，不依賴時序運氣。

## 修過頭的風險

樂觀條件加錯地方會誤擋合法操作——那比漏擋更糟（漏擋只是維持現狀，誤擋是製造
新故障）。所以本檔的**第一優先是釘住正常路徑仍然通過**（`test_*_happy_path`），
沒有那幾條，這個修正可能靜默打壞正常的狀態流轉。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import work_order_service

pytestmark = pytest.mark.component

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo(status: str, with_technician: bool = True) -> tuple[str, str, str]:
    """建 (user_id, technician_id, work_order_id)，工單為指定 status。"""
    assert await db_module._ensure_conn(), "需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    user_id, tech_id = str(uuid.uuid4()), str(uuid.uuid4())
    wo_id, pc_id = str(uuid.uuid4()), str(uuid.uuid4())

    await conn.execute(
        "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'x', 'technician', TRUE) ON CONFLICT (id) DO NOTHING",
        (user_id, DEFAULT_TENANT_ID, f"racer-{user_id[:8]}@example.com"),
    )
    await conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '競態測試技師', %s, 'active') "
        "ON CONFLICT (id) DO NOTHING",
        (tech_id, DEFAULT_TENANT_ID, user_id, f"09{tech_id[:8]}"),
    )
    await conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, source, knowledge_ready, brand) "
        "VALUES (%s::uuid, %s::uuid, 'manual', FALSE, 'Chatlock') ON CONFLICT (id) DO NOTHING",
        (pc_id, DEFAULT_TENANT_ID),
    )
    await conn.execute(
        "INSERT INTO work_orders "
        "  (id, problem_card_id, tenant_id, status, priority, technician_id, "
        "   customer_name, customer_phone, customer_address, created_by) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'normal', %s, "
        "        '競態客戶', '0900000000', '台北市測試路 1 號', %s::uuid)",
        (wo_id, pc_id, DEFAULT_TENANT_ID, status,
         tech_id if with_technician else None, user_id),
    )
    return user_id, tech_id, wo_id


async def _status_of(wo_id: str) -> tuple[str, str | None]:
    cur = await db_module._conn.execute(
        "SELECT status, technician_id FROM work_orders WHERE id = %s::uuid", (wo_id,)
    )
    row = await cur.fetchone()
    return row[0], (str(row[1]) if row[1] else None)


def _inject_race(monkeypatch, *, new_status: str, new_tech: str | None = "KEEP"):
    """讓 _fetch_status_for_update 回傳過期值：回傳前先把 DB 改成 new_status。

    模擬「另一個請求在我讀完 status 之後、寫入之前，已經完成了它的 transition」。
    """
    original = work_order_service._fetch_status_for_update

    async def racing(wo_id: str, tenant_id: str) -> str:
        stale = await original(wo_id, tenant_id)   # 先取得真實的當前狀態
        if new_tech == "KEEP":
            await db_module._conn.execute(
                "UPDATE work_orders SET status = %s WHERE id = %s::uuid", (new_status, wo_id)
            )
        else:
            await db_module._conn.execute(
                "UPDATE work_orders SET status = %s, technician_id = %s WHERE id = %s::uuid",
                (new_status, new_tech, wo_id),
            )
        return stale                                # 回傳「過期」的值給呼叫端

    monkeypatch.setattr(work_order_service, "_fetch_status_for_update", racing)


# =============================================================================
# 第一優先：正常路徑必須不受影響（防止修過頭）
# =============================================================================


async def test_reject_happy_path_still_works():
    """無競態時拒單照常成功——樂觀條件不可誤擋正常流程。"""
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    await work_order_service.reject_order(
        tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id, reason="今日已滿檔",
        actor_user_id=user_id, actor_role="technician",
    )
    status, tech = await _status_of(wo_id)
    assert status == "created", "拒單後應回派工池"
    assert tech is None, "拒單後應清空 technician_id"


async def test_accept_happy_path_still_works():
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    await work_order_service.accept_order(
        tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id,
        actor_user_id=user_id, actor_role="technician",
    )
    status, _ = await _status_of(wo_id)
    assert status == "accepted"


# =============================================================================
# 競態：狀態在讀取與寫入之間被改變 → 必須 409，不可覆寫
# =============================================================================


async def test_reject_loses_race_to_cancel(monkeypatch):
    """技師拒單 vs 客戶取消：拒單不可把已 cancelled 的單打回派工池。

    修正前：reject 拿著過期的 'assigned' 通過守衛，UPDATE 無條件執行，
    status 被改回 'created'——**已取消的單重新出現在派工池**。
    """
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    _inject_race(monkeypatch, new_status="cancelled")

    with pytest.raises(ApiError) as exc:
        await work_order_service.reject_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id, reason="今日已滿檔",
            actor_user_id=user_id, actor_role="technician",
        )
    assert exc.value.status_code == 409, "狀態已被他人改變，應回 409 讓呼叫端重試"

    status, _ = await _status_of(wo_id)
    assert status == "cancelled", "取消的結果必須保留，不可被拒單覆寫"


async def test_reject_loses_race_to_reassign(monkeypatch):
    """技師拒單 vs 小編改派——**這條在修正前就已經是綠的**。

    CR-0199 §4.2 原本把這個組合當成主案例，但實測證明它是錯的：`reject_order`
    在 UPDATE 之前會另外查一次 `technician_id` 並比對
    （`if tech_id != tech_ctx["id"]: raise 409`），改派已經換掉了 technician_id，
    所以這條路徑**既有 code 就擋得住**。

    保留本測試的理由是**釘住這個既有保護不可退化**——加樂觀條件時若不小心把那段
    擁有權比對重構掉，這裡會立刻變紅。

    真正會失效的是「status 改變但 technician_id 不變」的異型組合，
    見上下的 `*_loses_race_to_cancel` 與 `test_cancel_loses_race_to_complete`。
    """
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    other_tech = str(uuid.uuid4())
    other_user = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'x', 'technician', TRUE) ON CONFLICT (id) DO NOTHING",
        (other_user, DEFAULT_TENANT_ID, f"other-{other_user[:8]}@example.com"),
    )
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '技師B', %s, 'active') ON CONFLICT (id) DO NOTHING",
        (other_tech, DEFAULT_TENANT_ID, other_user, f"09{other_tech[:8]}"),
    )
    # 競態：改派給 B（status 仍是 assigned，但 technician_id 換人）
    _inject_race(monkeypatch, new_status="assigned", new_tech=other_tech)

    with pytest.raises(ApiError) as exc:
        await work_order_service.reject_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id, reason="今日已滿檔",
            actor_user_id=user_id, actor_role="technician",
        )
    # 改派後這張單已不屬於原技師 → 既有的擁有權檢查就會擋下（409）
    assert exc.value.status_code == 409

    status, tech = await _status_of(wo_id)
    assert status == "assigned", "改派結果必須保留"
    assert tech == other_tech, "工單必須仍指派給技師 B，不可被打回池"


async def test_accept_loses_race_to_cancel(monkeypatch):
    """技師接單 vs 客戶取消：接單不可讓已取消的單變成 accepted。"""
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    _inject_race(monkeypatch, new_status="cancelled")

    with pytest.raises(ApiError) as exc:
        await work_order_service.accept_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id,
            actor_user_id=user_id, actor_role="technician",
        )
    assert exc.value.status_code == 409

    status, _ = await _status_of(wo_id)
    assert status == "cancelled", "取消的結果必須保留"


async def test_cancel_loses_race_to_complete(monkeypatch):
    """客戶取消 vs 技師完工：取消不可覆蓋已完工的單。"""
    user_id, tech_id, wo_id = await _seed_wo("in_progress")
    _inject_race(monkeypatch, new_status="completed")

    with pytest.raises(ApiError) as exc:
        await work_order_service.cancel_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id, reason="客戶臨時取消",
            actor_user_id=user_id,
        )
    assert exc.value.status_code == 409

    status, _ = await _status_of(wo_id)
    assert status == "completed", "完工結果必須保留，不可被取消覆寫"
