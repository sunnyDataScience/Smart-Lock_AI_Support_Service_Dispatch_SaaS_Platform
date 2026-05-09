"""F-017 createSopDraft integration tests（自進化異步寫入路徑）。

測試矩陣：
  1. Happy path: PC + draft_content + model_version → 201 + SOP-YYYYMMDD-NNNN doc
  2. Idempotency: 同 (problem_card_id, model_version) 二次 → 200 + 同 id
  3. 不同 model_version 同 PC → 兩筆獨立 (允許多版本 draft)
  4. Validation: missing draft_content → 422
  5. Validation: missing model_version → 422
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def insert_pc(client):
    """建 user→conversation→PC chain，回 pc_id（SOP source）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"pc": [], "conv": [], "user": []}

    async def _factory(*, tenant_id: str = DEFAULT_TENANT_ID) -> str:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, role) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user')",
            (user_id, tenant_id, f"U{user_id.replace('-', '')}"),
        )
        created["user"].append(user_id)
        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, user_id, f"sop-test-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDR-1', 'resolved')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)
        return pc_id

    yield _factory

    await _ensure_conn()
    for pc_id in created["pc"]:
        await db_module._conn.execute(
            "DELETE FROM sop_drafts WHERE source_problem_card_id = %s::uuid",
            (pc_id,),
        )
    for table, ids in [
        ("problem_cards", created["pc"]),
        ("conversations", created["conv"]),
        ("users", created["user"]),
    ]:
        if ids:
            await db_module._conn.execute(
                f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,)
            )


@pytest.mark.asyncio
async def test_create_happy_path(client, admin_headers, insert_pc):
    pc_id = await insert_pc()
    res = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "source_case_id": pc_id,
            "source_type": "problem_card",
            "draft_content": "## SOP\n1. step 1\n2. step 2",
            "model_version": "gemini-2.5-pro-test",
            "confidence_score": 0.85,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["problem_card_id"] == pc_id
    assert data["status"] == "under_review"


@pytest.mark.asyncio
async def test_create_idempotent_same_model_version(
    client, admin_headers, insert_pc,
):
    pc_id = await insert_pc()
    body = {
        "source_case_id": pc_id,
        "source_type": "problem_card",
        "draft_content": "first version",
        "model_version": "model-v1",
    }
    res1 = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert res1.status_code == 201
    sid1 = res1.json()["data"]["id"]

    res2 = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**body, "draft_content": "different content (ignored)"},
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == sid1


@pytest.mark.asyncio
async def test_create_diff_model_version_creates_new(
    client, admin_headers, insert_pc,
):
    pc_id = await insert_pc()
    base = {
        "source_case_id": pc_id,
        "source_type": "problem_card",
        "draft_content": "x",
    }
    res1 = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**base, "model_version": "v1"},
    )
    res2 = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**base, "model_version": "v2"},
    )
    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["data"]["id"] != res2.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_validation_missing_draft_content(client, admin_headers):
    res = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "source_case_id": str(uuid.uuid4()),
            "source_type": "problem_card",
            "model_version": "v1",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_validation_missing_model_version(client, admin_headers):
    res = await client.post(
        "/api/v1/sop-drafts",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "source_case_id": str(uuid.uuid4()),
            "source_type": "problem_card",
            "draft_content": "x",
        },
    )
    assert res.status_code == 422
