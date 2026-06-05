"""Dispute resolution_amount < 0 → admin manual review trail (HD-4 解 DEFERRED)。

不依賴 DB / WS：
- _emit_negative_resolution_event 呼 audit_log_service + ws_hub
- audit_log_service 失敗不 leak 例外
- ws_hub 失敗不 leak 例外
- payload 含 dispute_id / amount / action_required / co_signer_id
"""

from __future__ import annotations

import pytest

from services import dispute_v2_service as svc


@pytest.mark.asyncio
async def test_negative_resolution_writes_audit_log(monkeypatch):
    captured = {}

    async def fake_audit(**kwargs):
        captured.update(kwargs)

    from services import audit_log_service
    monkeypatch.setattr(audit_log_service, "log_event", fake_audit)

    class FakeHub:
        async def publish(self, channel, msg):
            pass

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._emit_negative_resolution_event(
        tenant_id="t1", dispute_id="d1", co_signer_id="user-1", amount=-500.0,
    )
    assert captured["event_type"] == "dispute.negative_resolution_pending"
    assert captured["target_type"] == "dispute"
    assert captured["target_id"] == "d1"
    assert captured["actor_id"] == "user-1"
    assert captured["actor_role"] == "ops_manager"
    assert captured["action"] == "negative_resolution_audit"
    payload = captured["payload"]
    assert payload["dispute_id"] == "d1"
    assert payload["resolution_amount"] == -500.0
    assert payload["co_signer_id"] == "user-1"
    assert payload["action_required"] == "manual_refund_review"
    assert "manually review" in payload["note"]


@pytest.mark.asyncio
async def test_negative_resolution_ws_publishes_to_dispute_channel(monkeypatch):
    """channel 對齊 tenant：/realtime/disputes/{tenant_id}。"""
    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    from services import audit_log_service
    async def fake_audit(**kwargs):
        pass
    monkeypatch.setattr(audit_log_service, "log_event", fake_audit)

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._emit_negative_resolution_event(
        tenant_id="tenant-99", dispute_id="d1", co_signer_id="u1", amount=-100.0,
    )
    assert len(published) == 1
    channel, msg = published[0]
    assert channel == "/realtime/disputes/tenant-99"
    assert msg["type"] == "dispute.negative_resolution_pending"
    assert msg["payload"]["dispute_id"] == "d1"


@pytest.mark.asyncio
async def test_negative_resolution_audit_failure_swallowed(monkeypatch):
    """audit_log_service 拋例外 → 仍嘗試 publish；不該 raise。"""
    async def fake_audit(**kwargs):
        raise RuntimeError("audit DB down")

    from services import audit_log_service
    monkeypatch.setattr(audit_log_service, "log_event", fake_audit)

    published = []

    class FakeHub:
        async def publish(self, channel, msg):
            published.append((channel, msg))

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    # 不該 raise
    await svc._emit_negative_resolution_event(
        tenant_id="t1", dispute_id="d1", co_signer_id="u1", amount=-50.0,
    )
    # publish 仍嘗試
    assert len(published) == 1


@pytest.mark.asyncio
async def test_negative_resolution_ws_failure_swallowed(monkeypatch):
    """ws_hub.publish 拋例外 → 不該 leak。"""
    async def fake_audit(**kwargs):
        pass

    from services import audit_log_service
    monkeypatch.setattr(audit_log_service, "log_event", fake_audit)

    class FakeHub:
        async def publish(self, channel, msg):
            raise RuntimeError("WS down")

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._emit_negative_resolution_event(
        tenant_id="t1", dispute_id="d1", co_signer_id="u1", amount=-50.0,
    )


@pytest.mark.asyncio
async def test_amount_rounded_to_2_decimals(monkeypatch):
    """amount=-123.456 → payload.resolution_amount=-123.46"""
    captured = {}

    async def fake_audit(**kwargs):
        captured.update(kwargs)

    from services import audit_log_service
    monkeypatch.setattr(audit_log_service, "log_event", fake_audit)

    class FakeHub:
        async def publish(self, channel, msg):
            pass

    import realtime.ws_hub as ws_hub
    monkeypatch.setattr(ws_hub, "hub", FakeHub())

    await svc._emit_negative_resolution_event(
        tenant_id="t1", dispute_id="d1", co_signer_id="u1", amount=-123.456,
    )
    assert captured["payload"]["resolution_amount"] == -123.46
