"""CR-0017 Stage 5 — LINE webhook signature + postback dispatch tests。

驗證：
- _verify_signature: 正/錯/缺/dev fallback
- _handle_postback: 4 種短碼正確分派 (monkeypatch service)
- POST /api/v1/line/webhook: 401 on bad signature, 200 on good
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from routers import line_webhook as webhook_module


# ----------------------------- signature -----------------------------

def _make_sig(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(mac).decode("utf-8")


def test_verify_signature_valid(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret-1234")
    body = b'{"events":[]}'
    sig = _make_sig("test-secret-1234", body)
    assert webhook_module._verify_signature(body, sig) is True


def test_verify_signature_wrong(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret-1234")
    assert webhook_module._verify_signature(b'{"events":[]}', "wrong-sig") is False


def test_verify_signature_missing_header(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret-1234")
    assert webhook_module._verify_signature(b'{"events":[]}', None) is False


def test_verify_signature_no_secret_fail_closed(monkeypatch):
    """R24: 缺 LINE_CHANNEL_SECRET 且無 dev 旗標 → fail-closed 拒絕(不再放行)。"""
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("ALLOW_UNSIGNED_LINE_WEBHOOK", raising=False)
    assert webhook_module._verify_signature(b'{"events":[]}', None) is False


def test_verify_signature_no_secret_dev_passthrough(monkeypatch):
    """dev mode: 明確設 ALLOW_UNSIGNED_LINE_WEBHOOK=1 時,缺 secret 才放行(R24)。"""
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.setenv("ALLOW_UNSIGNED_LINE_WEBHOOK", "1")
    assert webhook_module._verify_signature(b'{"events":[]}', None) is True


# ----------------------------- postback dispatch -----------------------------

@pytest.mark.asyncio
async def test_handle_postback_reschedule_confirm(monkeypatch):
    called = {}

    async def fake_confirm(*, proposal_id, slot_idx):
        called["confirm"] = (proposal_id, slot_idx)
        return {"ok": True}

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "confirm_reschedule_by_proposal",
        fake_confirm,
    )
    await webhook_module._handle_postback({
        "type": "postback",
        "source": {"userId": "U1234"},
        "postback": {"data": "r:c|aaaa-bbbb-cccc-dddd|2"},
    })
    assert called["confirm"] == ("aaaa-bbbb-cccc-dddd", 2)


@pytest.mark.asyncio
async def test_handle_postback_reschedule_reject(monkeypatch):
    called = {}

    async def fake_reject(*, proposal_id):
        called["reject"] = proposal_id

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "reject_reschedule_by_proposal",
        fake_reject,
    )
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "r:r|prop-uuid-1"},
    })
    assert called["reject"] == "prop-uuid-1"


@pytest.mark.asyncio
async def test_handle_postback_scope_change_accept(monkeypatch):
    called = {}

    async def fake_respond(*, proposal_id, decision, **kwargs):
        called["respond"] = (proposal_id, decision)
        return {"ok": True}

    monkeypatch.setattr(
        webhook_module.scope_change_service, "respond_public", fake_respond,
    )
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "s:a|scope-uuid-1"},
    })
    assert called["respond"] == ("scope-uuid-1", "accept")


@pytest.mark.asyncio
async def test_handle_postback_scope_change_reject(monkeypatch):
    called = {}

    async def fake_respond(*, proposal_id, decision, **kwargs):
        called["respond"] = (proposal_id, decision)

    monkeypatch.setattr(
        webhook_module.scope_change_service, "respond_public", fake_respond,
    )
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "s:r|scope-uuid-2"},
    })
    assert called["respond"] == ("scope-uuid-2", "reject")


@pytest.mark.asyncio
async def test_handle_postback_unknown_kind_logs_no_crash():
    """未知短碼不該 raise — log warning 即可。"""
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "xxx:yyy|whatever"},
    })


@pytest.mark.asyncio
async def test_handle_postback_service_exception_swallowed(monkeypatch):
    """Service 拋例外不該阻斷其他 event（CR-0017 設計：LINE 不會 retry HTTP 200，
    冪等由 service CAS 保證）。"""
    async def fake_raise(**kwargs):
        raise RuntimeError("DB down")

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "confirm_reschedule_by_proposal",
        fake_raise,
    )
    # 不該 raise
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "r:c|p1|0"},
    })


# ----------------------------- HTTP endpoint -----------------------------

@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_webhook_post_rejects_bad_signature(monkeypatch, client):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    resp = await client.post(
        "/api/v1/line/webhook",
        content=b'{"events":[]}',
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": "wrong",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_post_accepts_valid_signature(monkeypatch, client):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    body = b'{"events":[]}'
    sig = _make_sig("test-secret", body)
    resp = await client.post(
        "/api/v1/line/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "processed": 0}


@pytest.mark.asyncio
async def test_webhook_post_dispatches_postback_event(monkeypatch, client):
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)  # dev mode
    monkeypatch.setenv("ALLOW_UNSIGNED_LINE_WEBHOOK", "1")  # R24: dev 放行需明確旗標

    called = {}

    async def fake_confirm(*, proposal_id, slot_idx):
        called["confirm"] = (proposal_id, slot_idx)

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "confirm_reschedule_by_proposal",
        fake_confirm,
    )

    body = json.dumps({
        "events": [{
            "type": "postback",
            "source": {"userId": "Uabc"},
            "postback": {"data": "r:c|p-1234|0"},
        }],
    }).encode()
    resp = await client.post(
        "/api/v1/line/webhook",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] == 1
    assert called["confirm"] == ("p-1234", 0)


@pytest.mark.asyncio
async def test_webhook_post_rejects_invalid_json(monkeypatch, client):
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.setenv("ALLOW_UNSIGNED_LINE_WEBHOOK", "1")  # R24: dev 放行需明確旗標
    resp = await client.post(
        "/api/v1/line/webhook",
        content=b"{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_post_no_secret_no_flag_fail_closed(monkeypatch, client):
    """R24: 缺 secret 且無 ALLOW_UNSIGNED 旗標 → 端到端 401(fail-closed)。"""
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("ALLOW_UNSIGNED_LINE_WEBHOOK", raising=False)
    resp = await client.post(
        "/api/v1/line/webhook",
        content=b'{"events":[]}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_handle_postback_empty_data_no_dispatch(monkeypatch):
    """R28: 空 postback data → 不分派任何 handler、不 crash(dead branch 修正)。"""
    called = {}

    async def fake_confirm(**kwargs):
        called["hit"] = True

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "confirm_reschedule_by_proposal",
        fake_confirm,
    )
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": ""},
    })
    assert "hit" not in called


@pytest.mark.asyncio
async def test_handle_postback_malformed_slot_idx_no_dispatch(monkeypatch):
    """R27: r:c slot_idx 非數字 → 不呼叫 confirm(不落 broad except 的冪等假設)。"""
    called = {}

    async def fake_confirm(**kwargs):
        called["hit"] = True

    monkeypatch.setattr(
        webhook_module.work_order_service,
        "confirm_reschedule_by_proposal",
        fake_confirm,
    )
    await webhook_module._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "r:c|p-1234|abc"},
    })
    assert "hit" not in called
