"""Pool realtime publish contract — backend ↔ frontend pool/page.tsx 對齊。

驗證 `_publish_pool_change` helper：
  - event='added' 帶 work_order 物件
  - event='taken' / 'cancelled' 只帶 work_order_id
  - technician_id 為空時 no-op
  - 失敗不 raise（best-effort）

不依賴 DB / ws_hub real implementation — 全 monkey-patch。
"""

from __future__ import annotations

import pytest

from services import work_order_service as svc


@pytest.mark.asyncio
async def test_publish_pool_added_includes_work_order(monkeypatch):
    """event=added → payload 必含 work_order 物件供前端 prepend。"""
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    async def fake_get_order(*, tenant_id, wo_id):
        return {"id": wo_id, "status": "assigned", "tenant_id": tenant_id}

    # patch hub import inside _publish_pool_change
    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())
    monkeypatch.setattr(svc, "get_order", fake_get_order)

    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="tech-1", event="added",
    )

    assert len(published) == 1
    channel, msg = published[0]
    assert channel == "/realtime/pool/tech-1"
    assert msg["type"] == "work_order.pool_added"
    payload = msg["payload"]
    assert payload["event"] == "added"
    assert payload["work_order_id"] == "w1"
    assert payload["work_order"] == {
        "id": "w1", "status": "assigned", "tenant_id": "t1",
    }


@pytest.mark.asyncio
async def test_publish_pool_taken_only_work_order_id(monkeypatch):
    """event=taken → 只需 work_order_id（前端 filter 移除）。"""
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="tech-1", event="taken",
    )

    assert published[0][1]["payload"] == {"event": "taken", "work_order_id": "w1"}
    # taken 不該帶 work_order key
    assert "work_order" not in published[0][1]["payload"]


@pytest.mark.asyncio
async def test_publish_pool_cancelled_only_work_order_id(monkeypatch):
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="tech-1", event="cancelled",
    )

    payload = published[0][1]["payload"]
    assert payload["event"] == "cancelled"
    assert payload["work_order_id"] == "w1"
    assert "work_order" not in payload


@pytest.mark.asyncio
async def test_publish_pool_no_tech_id_is_noop(monkeypatch):
    """technician_id 為空 → 不該 publish (避免造 /realtime/pool/None 髒 channel)。"""
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="", event="added",
    )
    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id=None, event="taken",  # type: ignore[arg-type]
    )

    assert published == []


@pytest.mark.asyncio
async def test_publish_pool_get_order_failure_still_publishes(monkeypatch):
    """get_order 拋 → publish 仍要進行（不帶 work_order 但仍推出去）。"""
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    async def fake_get_order(**kwargs):
        raise RuntimeError("DB down")

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())
    monkeypatch.setattr(svc, "get_order", fake_get_order)

    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="tech-1", event="added",
    )

    # 仍 publish 但 work_order 缺
    assert len(published) == 1
    payload = published[0][1]["payload"]
    assert payload["event"] == "added"
    assert payload["work_order_id"] == "w1"
    assert "work_order" not in payload  # get_order 失敗則省略


@pytest.mark.asyncio
async def test_publish_pool_hub_publish_failure_swallowed(monkeypatch):
    """hub.publish 拋 → 不該 leak 例外（best-effort）。"""
    class FakeHub:
        async def publish(self, *args, **kwargs):
            raise RuntimeError("WS down")

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    # 不該 raise
    await svc._publish_pool_change(
        tenant_id="t1", wo_id="w1", technician_id="tech-1", event="taken",
    )
