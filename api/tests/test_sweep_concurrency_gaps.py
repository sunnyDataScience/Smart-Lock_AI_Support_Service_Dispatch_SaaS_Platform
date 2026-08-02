"""CR-0199 沒涵蓋到的兩條併發路徑（2026-08-02 全維度掃描）。

CR-0199 修的是 `work_order_service` 與 `problem_card_service` 的 transition，
但掃描發現同一個 check-then-act 模式還存在於兩處**更敏感**的路徑：

## ① `reconciliation_service.reject_reconciliation`

CR-0189 把 `approve_reconciliation` 包成 `transaction()` + `FOR UPDATE OF r`，
但 `reject_reconciliation` 是後來 UAT-0718 W1-2 才加的獨立路徑，不在該次範圍。
**純 SELECT 不會被 `FOR UPDATE` 擋住**，所以兩支端點在 approve/reject 並發時可以
雙雙通過各自的 pending 檢查：approve 先 commit（已寫入 `settlements` 並投遞
`commission.accrued`），reject 隨後把狀態覆寫成 `rejected`。

結果＝**營運端看到「已駁回」但技師照樣被結算出款**，而該列此時的 `rejected`
兩支端點都只回 409，API 層沒有撤銷那筆 settlement 的路徑。

## ② `cancellation_service.cancel_work_order_6stage`

v2 六階段取消**不經** `work_order_service.cancel_order`（該檔的 CR-0193 註解自述），
所以 CR-0199 加在 work_order_service 的樂觀鎖被**從反方向繞過**：
技師送完工的同時客服取消 → 完工端寫入 `completed`，取消端隨後無條件覆寫成
`cancelled`。實際已完工的工單被翻成取消，**客戶照收 S3/S4 取消費、技師照記罰則**。

---

測試手法同 `test_state_machine_optimistic_lock.py`：精確競態窗口注入，
在讀完狀態之後、寫入之前改 DB，每次必然重現、不依賴時序運氣。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import cancellation_service
from services.cancellation_service import DEFAULT_CANCELLATION_CONFIG

pytestmark = pytest.mark.component

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo(status: str) -> tuple[str, str, str]:
    assert await db_module._ensure_conn(), "需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    user_id, tech_id = str(uuid.uuid4()), str(uuid.uuid4())
    wo_id, pc_id = str(uuid.uuid4()), str(uuid.uuid4())

    await conn.execute(
        "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'x', 'technician', TRUE) ON CONFLICT (id) DO NOTHING",
        (user_id, DEFAULT_TENANT_ID, f"cx-{user_id[:8]}@example.com"),
    )
    await conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '取消測試技師', %s, 'active') "
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
        "   customer_name, customer_phone, customer_address, created_by, "
        "   brand, model, problem_type, scheduled_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'normal', %s::uuid, "
        "        '取消測試客戶', '0900000000', '台北市測試路 2 號', %s::uuid, "
        "        'Chatlock', 'CL-100', '無法開鎖', NOW() + INTERVAL '2 days')",
        (wo_id, pc_id, DEFAULT_TENANT_ID, status, tech_id, user_id),
    )
    return user_id, tech_id, wo_id


async def _status_of(wo_id: str) -> str:
    cur = await db_module._conn.execute(
        "SELECT status FROM work_orders WHERE id = %s::uuid", (wo_id,)
    )
    return (await cur.fetchone())[0]


async def _cancel(wo_id: str, actor_id: str) -> dict:
    """以 router 的同一組參數呼叫六階段取消（SoD 三方用不同 id 以通過職責分離檢查）。"""
    return await cancellation_service.cancel_work_order_6stage(
        tenant_id=DEFAULT_TENANT_ID,
        wo_id=wo_id,
        reason_code="dispatched_not_departed",
        initiator_role="customer",
        goodwill_waiver=False,
        evidence_ids=None,
        note=None,
        distance_km=None,
        cancellation_config=DEFAULT_CANCELLATION_CONFIG,
        config_version="default",
        sod_initiator=str(uuid.uuid4()),
        sod_approver=str(uuid.uuid4()),
        sod_executor=str(uuid.uuid4()),
        actor_id=actor_id,
        actor_role="admin",
    )


def _inject_race(monkeypatch, wo_id: str, *, becomes: str):
    """讓 _fetch_wo_for_cancel 回傳過期快照：回傳前先把 DB 改成 becomes。"""
    original = cancellation_service._fetch_wo_for_cancel

    async def racing(w: str, t: str):
        stale = await original(w, t)
        await db_module._conn.execute(
            "UPDATE work_orders SET status = %s WHERE id = %s::uuid", (becomes, wo_id)
        )
        return stale

    monkeypatch.setattr(cancellation_service, "_fetch_wo_for_cancel", racing)


# =============================================================================
# 第一優先：正常取消仍然要成功（防止修過頭）
# =============================================================================


async def test_cancel_6stage_happy_path_still_works():
    user_id, tech_id, wo_id = await _seed_wo("assigned")
    await _cancel(wo_id, user_id)
    assert await _status_of(wo_id) == "cancelled"


# =============================================================================
# 競態：取消不可覆寫終態
# =============================================================================


async def test_cancel_6stage_cannot_overwrite_completed(monkeypatch):
    """技師完工 vs 客服取消——已完工的單被翻成 cancelled 會誤收取消費與誤記罰則。"""
    user_id, tech_id, wo_id = await _seed_wo("in_progress")
    _inject_race(monkeypatch, wo_id, becomes="completed")

    with pytest.raises(ApiError) as exc:
        await _cancel(wo_id, user_id)
    assert exc.value.status_code == 409

    assert await _status_of(wo_id) == "completed", "完工結果必須保留"


async def test_cancel_6stage_cannot_overwrite_confirmed(monkeypatch):
    """客戶確認結案後同樣不可被取消覆寫。"""
    user_id, tech_id, wo_id = await _seed_wo("in_progress")
    _inject_race(monkeypatch, wo_id, becomes="confirmed")

    with pytest.raises(ApiError) as exc:
        await _cancel(wo_id, user_id)
    assert exc.value.status_code == 409
    assert await _status_of(wo_id) == "confirmed"
