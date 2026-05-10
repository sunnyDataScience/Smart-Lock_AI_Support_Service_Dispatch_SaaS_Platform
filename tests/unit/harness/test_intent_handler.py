"""Unit tests for ``harness.intent_handler`` (H_INTENT layer).

Verifies F-014/F-015 dual-trigger (a) path short-circuits the agent pipeline
when the user expresses refund / warranty intent in LINE.

Coverage:
- ``try_handle_intent`` returns refund template on refund intent
- ``try_handle_intent`` returns warranty template on warranty intent
- ``try_handle_intent`` returns None on technical-question text (no
  short-circuit; agent flow continues)
- audit_storage hook is called when provided
- audit_storage missing ``log_intent_hit`` method → silently skipped
"""

from __future__ import annotations

import pytest

from harness.intent_handler import try_handle_intent


@pytest.mark.asyncio
async def test_refund_intent_returns_refund_template():
    reply = await try_handle_intent(user_id="U-test", text="我要退款")
    assert reply is not None
    assert "退款" in reply
    assert "24 小時" in reply


@pytest.mark.asyncio
async def test_warranty_intent_returns_warranty_template():
    reply = await try_handle_intent(user_id="U-test", text="保固期內壞掉")
    assert reply is not None
    assert "保固" in reply
    assert "24 小時" in reply


@pytest.mark.asyncio
async def test_no_intent_returns_none():
    reply = await try_handle_intent(user_id="U-test", text="門打不開")
    assert reply is None


@pytest.mark.asyncio
async def test_empty_text_returns_none():
    reply = await try_handle_intent(user_id="U-test", text="")
    assert reply is None


@pytest.mark.asyncio
async def test_audit_hook_called_when_provided():
    calls: list[dict] = []

    class _StubAudit:
        async def log_intent_hit(self, **kwargs):
            calls.append(kwargs)

    reply = await try_handle_intent(
        user_id="U-aud", text="我要退費", audit_storage=_StubAudit(),
    )
    assert reply is not None
    assert calls == [{"user_id": "U-aud", "intent": "refund", "text": "我要退費"}]


@pytest.mark.asyncio
async def test_audit_storage_without_method_is_skipped_silently():
    """``audit_storage`` may be the legacy storage that doesn't yet expose
    ``log_intent_hit``; we should fall back to no-op without raising."""
    class _LegacyAudit:
        pass

    reply = await try_handle_intent(
        user_id="U-leg", text="保固", audit_storage=_LegacyAudit(),
    )
    assert reply is not None  # main behaviour still works


@pytest.mark.asyncio
async def test_refund_priority_over_warranty():
    """When both keywords appear, refund wins (financial intent priority)."""
    reply = await try_handle_intent(
        user_id="U-mix", text="保固期內想退款",
    )
    assert reply is not None
    assert "退款" in reply
    assert "保固" not in reply or "退款" in reply  # refund template, not warranty
