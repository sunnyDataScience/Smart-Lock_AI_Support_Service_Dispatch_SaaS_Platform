"""到場即開工（accepted → in_progress）— CR-0205 D1(a)。

⚠️ **需要 live DB**（record_arrival 直接打 work_orders）。撰寫當下本機無可用 postgres
（5433 是業主 UAT 庫，不可碰），故**尚未實跑驗證**——有測試庫時請優先跑這支。

WHY：`in_progress` 在此之前是死值。正常工單走 assigned → accepted → completed，
`_WO_TRANSITIONS` 裡 accepted→in_progress 那條邊沒有任何人走。連帶三個後果：
  ① 統計桶（work_order_service.py:590-604）的「施工中」恆為 0
  ② technician_service.py:512-518 的可派技師數把「人在現場施工」的師傅算成可派
     —— 營運看到的人力是高估的
  ③ requote_service._ALLOWED_WO_STATUS = {"in_progress"}（:23）→
     **現場加價整條路徑不可達**

業主已於 15_SDS.md:221 裁決 `on_site ≡ in_progress`，本修正是該裁決的落地。
"""
from __future__ import annotations

import pytest

from services import work_order_service as svc


@pytest.mark.asyncio
async def test_arrival_transitions_accepted_to_in_progress(make_wo):
    """accepted 狀態到場 → status 轉 in_progress，且 started_at 落點。"""
    wo = await make_wo(status="accepted")
    await svc.record_arrival(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    after = await svc.get_order(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    assert after["status"] == "in_progress", (
        "到場未轉施工中 —— in_progress 會退回死值，統計桶恆 0、"
        "可派技師數高估、現場加價不可達"
    )
    assert after.get("started_at")


@pytest.mark.asyncio
async def test_arrival_from_assigned_keeps_status(make_wo):
    """assigned 到場**刻意不轉**（技師未接單就到場屬異常流程，另議）。"""
    wo = await make_wo(status="assigned")
    await svc.record_arrival(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    after = await svc.get_order(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    assert after["status"] == "assigned"


@pytest.mark.asyncio
async def test_arrival_is_idempotent_on_in_progress(make_wo):
    """已在 in_progress 重複到場 → CASE 落 ELSE，維持原狀且不報錯。"""
    wo = await make_wo(status="accepted")
    await svc.record_arrival(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    await svc.record_arrival(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    after = await svc.get_order(tenant_id=wo["tenant_id"], wo_id=wo["id"])
    assert after["status"] == "in_progress"
