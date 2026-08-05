"""assign_dispatch 的 override_reason 傳參守線（CR-0204 D7，純單元、不需 DB）。

WHY：報價 gate（CR-0095 D2 業主裁決「派工前須有已同意報價」）的主管覆寫，
判定同時需要三個值——override_reason 有值 **且** actor_role 在
_QUOTE_GATE_OVERRIDE_ROLES 內。`dispatch_service.assign_dispatch` 原本把
override_reason 當成 reason_text 傳、且完全不傳 actor_role/actor_user_id，
於是**主管透過 /dispatch:assign 兩個端點帶 override_reason 急修派工，
覆寫完全不生效、照樣被 409 QUOTE_NOT_CUSTOMER_CONFIRMED 擋死**。

三個入口只有 work_orders_v2.assignWorkOrderV2 傳對了，另兩條都漏。
這種缺陷不會有任何錯誤訊息——參數安靜地跑到錯的地方去。
"""
from __future__ import annotations

import pytest

from services import dispatch_service


@pytest.mark.asyncio
async def test_assign_dispatch_forwards_override_and_actor(monkeypatch):
    """三個值都要原樣轉傳給 assign_order。"""
    seen: dict = {}

    async def _fake_assign_order(**kwargs):
        seen.update(kwargs)
        return {"id": kwargs["wo_id"], "status": "assigned"}

    import services.work_order_service as wos
    monkeypatch.setattr(wos, "assign_order", _fake_assign_order)

    await dispatch_service.assign_dispatch(
        tenant_id="t1", work_order_id="wo1", technician_id="tech1",
        override_reason="客戶已電話同意，急件先派", 
        actor_role="operations_manager", actor_user_id="u9",
    )

    assert seen["override_reason"] == "客戶已電話同意，急件先派", (
        "override_reason 沒有以覆寫身分傳下去 —— 主管急修派工會被 409 擋死"
    )
    assert seen["actor_role"] == "operations_manager"
    assert seen["actor_user_id"] == "u9"


@pytest.mark.asyncio
async def test_assign_dispatch_without_override_is_unchanged(monkeypatch):
    """反向：沒帶 override 時行為不變（不得因本次修正而改變一般派工路徑）。"""
    seen: dict = {}

    async def _fake_assign_order(**kwargs):
        seen.update(kwargs)
        return {"id": kwargs["wo_id"], "status": "assigned"}

    import services.work_order_service as wos
    monkeypatch.setattr(wos, "assign_order", _fake_assign_order)

    await dispatch_service.assign_dispatch(
        tenant_id="t1", work_order_id="wo1", technician_id="tech1")

    assert seen["override_reason"] is None
    assert seen["reason_code"] == "other"
