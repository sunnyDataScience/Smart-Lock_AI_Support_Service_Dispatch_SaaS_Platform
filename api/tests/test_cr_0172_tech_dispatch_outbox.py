"""CR-0172 — 技師派工推播改走 outbox unit tests(mocked,無需 DB/外呼)。

驗證(HD-A=A / HD-F flag):
- worker _process_row：tech_dispatch_assigned kind 走 _dispatch_to_tech(內部端點),
  不走客戶 LINE 直推 _push_to_line。
- worker _dispatch_to_tech：缺 env → (False, ...)。
- work_order_service _dispatch_tech_notify：flag 開 → enqueue；flag 關 → 舊同步 HTTP。
"""

from __future__ import annotations

import pytest

import services.line_push_outbox_service as lpos
import services.work_order_service as wos
from realtime.line_push_outbox_worker import LinePushOutboxWorker


@pytest.mark.asyncio
async def test_process_row_routes_tech_kind_to_internal_endpoint():
    """tech_dispatch_assigned → _dispatch_to_tech + _mark_sent,不觸客戶 LINE 直推。"""
    w = LinePushOutboxWorker()
    calls = {}

    async def fake_dispatch(push_kind, payload):
        calls["dispatch"] = (push_kind, payload)
        return True, None

    async def fake_mark_sent(oid):
        calls["sent"] = oid

    async def fake_push(*a, **k):
        calls["push"] = True
        return True, None

    w._dispatch_to_tech = fake_dispatch
    w._mark_sent = fake_mark_sent
    w._push_to_line = fake_push

    row = ("oid-1", "tenant-1", "tech_dispatch_assigned", None, "wo-1",
           "work_orders", {"technician_id": "t1"}, 0, 5)
    await w._process_row(row)

    assert calls["dispatch"][0] == "tech_dispatch_assigned"
    assert calls.get("sent") == "oid-1"
    assert "push" not in calls  # 未走客戶 LINE 直推


@pytest.mark.asyncio
async def test_process_row_customer_kind_still_uses_line_push(monkeypatch):
    """非技師 kind(客戶推播)維持走 _resolve_line_uid + _push_to_line(回歸)。"""
    w = LinePushOutboxWorker()
    calls = {}

    async def fake_resolve(*a, **k):
        return "Ucustomer"

    async def fake_push(line_uid, messages, retry_key=None):
        calls["push"] = line_uid
        return True, None

    async def fake_mark_sent(oid):
        calls["sent"] = oid

    async def fake_dispatch(*a, **k):
        calls["dispatch"] = True
        return True, None

    w._resolve_line_uid = fake_resolve
    w._push_to_line = fake_push
    w._mark_sent = fake_mark_sent
    w._dispatch_to_tech = fake_dispatch
    monkeypatch.setattr(
        "templates.line_flex.build_messages",
        lambda kind, payload: [{"type": "text", "text": "hi"}],
    )

    row = ("oid-2", "tenant-1", "work_order_assigned", None, "wo-2",
           "work_orders", {}, 0, 5)
    await w._process_row(row)

    assert calls.get("push") == "Ucustomer"
    assert "dispatch" not in calls  # 客戶 kind 不走技師分派


@pytest.mark.asyncio
async def test_dispatch_to_tech_missing_env(monkeypatch):
    """缺 TECH_API_BASE_URL/INTERNAL_API_TOKEN → (False, 未配置),交 outbox 重試。"""
    monkeypatch.delenv("TECH_API_BASE_URL", raising=False)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    w = LinePushOutboxWorker()
    ok, err = await w._dispatch_to_tech("tech_dispatch_assigned", {"technician_id": "t1"})
    assert ok is False
    assert "未配置" in err


@pytest.mark.asyncio
async def test_dispatch_tech_notify_flag_on_enqueues(monkeypatch):
    """HD-F flag 開 → enqueue(push_kind=tech_dispatch_assigned, ref=wo),不走舊同步。"""
    calls = {}

    async def fake_enqueue(**kw):
        calls["enqueue"] = kw
        return "oid"

    async def fake_notify(path, payload):
        calls["notify"] = (path, payload)

    monkeypatch.setenv("TECH_DISPATCH_VIA_OUTBOX", "1")
    monkeypatch.setattr(lpos, "enqueue", fake_enqueue)
    monkeypatch.setattr(wos, "_notify_tech_line", fake_notify)

    await wos._dispatch_tech_notify(
        tenant_id="t", wo_id="wo1", technician_id="tech1", wo_summary={"id": "wo1"},
    )
    assert calls["enqueue"]["push_kind"] == "tech_dispatch_assigned"
    assert calls["enqueue"]["reference_id"] == "wo1"
    assert calls["enqueue"]["reference_table"] == "work_orders"
    assert "notify" not in calls


@pytest.mark.asyncio
async def test_dispatch_tech_notify_flag_off_uses_sync(monkeypatch):
    """HD-F flag 關(預設)→ 走舊同步 _notify_tech_line,不 enqueue。"""
    calls = {}

    async def fake_enqueue(**kw):
        calls["enqueue"] = kw
        return "oid"

    async def fake_notify(path, payload):
        calls["notify"] = (path, payload)

    monkeypatch.delenv("TECH_DISPATCH_VIA_OUTBOX", raising=False)
    monkeypatch.setattr(lpos, "enqueue", fake_enqueue)
    monkeypatch.setattr(wos, "_notify_tech_line", fake_notify)

    await wos._dispatch_tech_notify(
        tenant_id="t", wo_id="wo1", technician_id="tech1", wo_summary={"id": "wo1"},
    )
    assert calls["notify"][0] == "/api/v1/internal/technicians/notify-assign"
    assert calls["notify"][1]["technician_id"] == "tech1"
    assert "enqueue" not in calls
