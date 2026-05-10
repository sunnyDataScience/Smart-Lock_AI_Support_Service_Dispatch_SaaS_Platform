"""Unit tests for ``harness.pc_creator`` (H_PC layer, F-001 PC auto-trigger).

Verifies the V1.0 minimum threshold gating logic:

- skip when ``conversation_id`` is None (cache miss)
- skip when ``device_brand`` is missing in facts
- skip when ``last_user_text`` is too short (noise filter)
- happy path: brand + symptom long enough → call AdminAPIClient.create_problem_card
- model defaults to "未知" when missing
- symptom truncated to 1000 chars
- idempotency_key follows ``{conversation_id}:F-001-pc`` spec
- AdminAPIClient exception fail-soft (returns None, doesn't raise)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from harness import pc_creator


@pytest.mark.asyncio
async def test_skip_when_no_conversation_id():
    result = await pc_creator.maybe_create_problem_card(
        user_id="U1",
        conversation_id=None,
        facts={"device_brand": "Chatlock"},
        last_user_text="門打不開很久了",
    )
    assert result is None


@pytest.mark.asyncio
async def test_skip_when_brand_missing():
    result = await pc_creator.maybe_create_problem_card(
        user_id="U1",
        conversation_id="conv-uuid-1",
        facts={},
        last_user_text="門打不開很久了",
    )
    assert result is None


@pytest.mark.asyncio
async def test_skip_when_text_too_short():
    result = await pc_creator.maybe_create_problem_card(
        user_id="U1",
        conversation_id="conv-uuid-1",
        facts={"device_brand": "Chatlock"},
        last_user_text="OK",  # 2 chars < min 4
    )
    assert result is None


@pytest.mark.asyncio
async def test_happy_path_creates_pc():
    fake_pc = {"id": "pc-uuid-1", "document_number": "PC-20260510-0001"}
    fake_client = AsyncMock()
    fake_client.create_problem_card = AsyncMock(return_value=fake_pc)

    with patch("integrations.AdminAPIClient") as MockClient:
        MockClient.from_env.return_value = fake_client

        result = await pc_creator.maybe_create_problem_card(
            user_id="U-line-001",
            conversation_id="conv-uuid-1",
            facts={"device_brand": "Chatlock", "device_model": "AI-99"},
            last_user_text="門卡住打不開好幾天了",
        )

    assert result == fake_pc
    fake_client.create_problem_card.assert_awaited_once()
    call_kwargs = fake_client.create_problem_card.await_args.kwargs
    assert call_kwargs["conversation_id"] == "conv-uuid-1"
    assert call_kwargs["brand"] == "Chatlock"
    assert call_kwargs["model"] == "AI-99"
    assert call_kwargs["symptom"] == "門卡住打不開好幾天了"
    assert call_kwargs["category"] == "故障"
    assert call_kwargs["urgency"] == "medium"
    assert call_kwargs["idempotency_key"] == "conv-uuid-1:F-001-pc"


@pytest.mark.asyncio
async def test_model_defaults_to_unknown_when_missing():
    fake_client = AsyncMock()
    fake_client.create_problem_card = AsyncMock(return_value={"id": "x"})

    with patch("integrations.AdminAPIClient") as MockClient:
        MockClient.from_env.return_value = fake_client
        await pc_creator.maybe_create_problem_card(
            user_id="U1",
            conversation_id="conv-2",
            facts={"device_brand": "Dormakaba"},  # no device_model
            last_user_text="鎖壞了無法使用",
        )

    call_kwargs = fake_client.create_problem_card.await_args.kwargs
    assert call_kwargs["model"] == "未知"


@pytest.mark.asyncio
async def test_symptom_truncated_to_1000_chars():
    long_text = "故障" * 600  # 1200 chars
    fake_client = AsyncMock()
    fake_client.create_problem_card = AsyncMock(return_value={"id": "x"})

    with patch("integrations.AdminAPIClient") as MockClient:
        MockClient.from_env.return_value = fake_client
        await pc_creator.maybe_create_problem_card(
            user_id="U1",
            conversation_id="conv-3",
            facts={"device_brand": "Chatlock"},
            last_user_text=long_text,
        )

    call_kwargs = fake_client.create_problem_card.await_args.kwargs
    assert len(call_kwargs["symptom"]) == 1000


@pytest.mark.asyncio
async def test_admin_api_exception_is_fail_soft():
    """AdminAPIClient internal exceptions must not propagate (fail-soft)."""
    fake_client = AsyncMock()
    fake_client.create_problem_card = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("integrations.AdminAPIClient") as MockClient:
        MockClient.from_env.return_value = fake_client
        result = await pc_creator.maybe_create_problem_card(
            user_id="U1",
            conversation_id="conv-4",
            facts={"device_brand": "Chatlock"},
            last_user_text="門鎖整個故障了",
        )

    assert result is None  # fail-soft: returns None instead of raising


@pytest.mark.asyncio
async def test_admin_api_returns_none_propagates_none():
    """AdminAPIClient returning None (after retries → outbox) → we also return None."""
    fake_client = AsyncMock()
    fake_client.create_problem_card = AsyncMock(return_value=None)

    with patch("integrations.AdminAPIClient") as MockClient:
        MockClient.from_env.return_value = fake_client
        result = await pc_creator.maybe_create_problem_card(
            user_id="U1",
            conversation_id="conv-5",
            facts={"device_brand": "Chatlock"},
            last_user_text="鎖完全打不開",
        )

    assert result is None
