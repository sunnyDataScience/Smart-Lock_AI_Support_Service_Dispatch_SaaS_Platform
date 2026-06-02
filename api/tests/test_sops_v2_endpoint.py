"""Component tests for SOPs Review v2 endpoints（CR-0003 P2-W3）。

測試矩陣：
  1. POST /sops/{id}/review/dual (approve) → 200 SopDraftEnvelope (Idempotency-Key)
  2. POST /sops/{id}/review/dual (reject)  → 200 SopDraftEnvelope
  3. POST /sops/{id}/review/dual on non-pending draft → 409 CONFLICT
  4. POST /sops/{id}/review/dual 未認證 → 401
  5. POST /sops/{id}/review/dual 找不到 → 404
  6. POST /sops/{id}/review/family → 200 FamilyReview (Idempotency-Key)
  7. POST /sops/{id}/review/family (dual review not done) → 425 TOO_EARLY
  8. POST /sops/{id}/review/family path/body id mismatch → 422
  9. POST /sops/{id}/review/family 未認證 → 401

注意：worktree 無真實 DB，component mark 測試在主 worktree 含 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


# ---------------------------------------------------------------------------
# Fixtures — 建 sop_draft 供各測試使用
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def insert_pending_draft(client):
    """建 user→conversation→PC→sop_draft(pending_review)，回 draft_id。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "drafts": [],
        "pc": [],
        "conv": [],
        "user": [],
    }

    async def _factory(*, tenant_id: str = DEFAULT_TENANT_ID) -> str:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, role) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user')",
            (user_id, tenant_id, f"U{user_id.replace('-', '')}"),
        )
        created["user"].append(user_id)

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, user_id, f"sops-v2-test-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)

        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDR-1', 'resolved')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)

        await db_module._conn.execute(
            "INSERT INTO sop_drafts "
            "(id, tenant_id, source_problem_card_id, title, steps, status, model_version, "
            " document_number) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, 'pending_review', %s, %s)",
            (
                draft_id,
                tenant_id,
                pc_id,
                "Yale YDR-1 處置流程",
                '[{"order":1,"title":"步驟一","description":"確認問題"}]',
                "test-model-v1",
                f"SOP-TEST-{draft_id[:8].upper()}",
            ),
        )
        created["drafts"].append(draft_id)
        return draft_id

    yield _factory

    # Teardown — cleanup in reverse FK order
    await _ensure_conn()
    for draft_id in created["drafts"]:
        await db_module._conn.execute(
            "DELETE FROM family_reviews WHERE sop_draft_id = %s::uuid",
            (draft_id,),
        )
        await db_module._conn.execute(
            "DELETE FROM sop_drafts WHERE id = %s::uuid",
            (draft_id,),
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


@pytest_asyncio.fixture
async def insert_approved_draft(client, insert_pending_draft, admin_headers):
    """建 pending draft 後透過 dual-review approve → 回 approved draft_id。"""

    async def _factory(*, tenant_id: str = DEFAULT_TENANT_ID) -> str:
        draft_id = await insert_pending_draft(tenant_id=tenant_id)
        # 直接用 service 改狀態（避免 duplicate test dependency）
        from core.db import _ensure_conn
        import core.db as db_module

        await _ensure_conn()
        await db_module._conn.execute(
            "UPDATE sop_drafts SET status = 'approved', reviewed_at = NOW() "
            "WHERE id = %s::uuid",
            (draft_id,),
        )
        return draft_id

    yield _factory


# ---------------------------------------------------------------------------
# 1. POST /sops/{id}/review/dual (approve) → 200 + Idempotency-Key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dual_review_approve_200(client, admin_headers, insert_pending_draft):
    """POST /sops/{id}/review/dual approve → 200 SopDraftEnvelope。"""
    draft_id = await insert_pending_draft()
    res = await client.post(
        f"/sops/{draft_id}/review/dual",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "comment": "LGTM"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "data" in data
    assert data["data"]["id"] == draft_id
    assert data["data"]["status"] == "approved"


# ---------------------------------------------------------------------------
# 2. POST /sops/{id}/review/dual (reject) → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dual_review_reject_200(client, admin_headers, insert_pending_draft):
    """POST /sops/{id}/review/dual reject → 200 SopDraftEnvelope。"""
    draft_id = await insert_pending_draft()
    res = await client.post(
        f"/sops/{draft_id}/review/dual",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "reject", "comment": "需修改步驟描述"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["data"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# 3. POST /sops/{id}/review/dual on non-pending draft → 409 CONFLICT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dual_review_non_pending_409(client, admin_headers, insert_approved_draft):
    """已 approved 的 draft 再次 dual review → 409 CONFLICT。"""
    draft_id = await insert_approved_draft()
    res = await client.post(
        f"/sops/{draft_id}/review/dual",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve"},
    )
    assert res.status_code == 409, res.text


# ---------------------------------------------------------------------------
# 4. POST /sops/{id}/review/dual 未認證 → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dual_review_unauthenticated_401(client):
    """缺 Authorization header → 401 UNAUTHENTICATED。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/sops/{fake_id}/review/dual",
        json={"decision": "approve"},
    )
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# 5. POST /sops/{id}/review/dual 找不到 → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dual_review_not_found_404(client, admin_headers):
    """不存在的 draft id → 404 NOT_FOUND。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/sops/{fake_id}/review/dual",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve"},
    )
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# 6. POST /sops/{id}/review/family → 200 FamilyReview (Idempotency-Key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_family_review_approved_200(
    client, admin_headers, insert_approved_draft
):
    """POST /sops/{id}/review/family approved → 200 FamilyReview。"""
    draft_id = await insert_approved_draft()
    res = await client.post(
        f"/sops/{draft_id}/review/family",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "sop_draft_id": draft_id,
            "action": "approved",
            "comment": "家族同意",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["action"] == "approved"
    assert data["sop_draft_id"] == draft_id


# ---------------------------------------------------------------------------
# 7. POST /sops/{id}/review/family on pending (dual not done) → 425 TOO_EARLY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_family_review_dual_not_done_425(
    client, admin_headers, insert_pending_draft
):
    """dual review 未完成 → 425 TOO_EARLY。"""
    draft_id = await insert_pending_draft()
    res = await client.post(
        f"/sops/{draft_id}/review/family",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "sop_draft_id": draft_id,
            "action": "approved",
        },
    )
    assert res.status_code == 425, res.text


# ---------------------------------------------------------------------------
# 8. POST /sops/{id}/review/family path/body mismatch → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_family_review_path_body_mismatch_422(
    client, admin_headers
):
    """path id 與 body.sop_draft_id 不一致 → 422 VALIDATION_ERROR。"""
    path_id = str(uuid.uuid4())
    body_id = str(uuid.uuid4())
    res = await client.post(
        f"/sops/{path_id}/review/family",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "sop_draft_id": body_id,
            "action": "approved",
        },
    )
    assert res.status_code == 422, res.text


# ---------------------------------------------------------------------------
# 9. POST /sops/{id}/review/family 未認證 → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_family_review_unauthenticated_401(client):
    """缺 Authorization header → 401 UNAUTHENTICATED。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/sops/{fake_id}/review/family",
        json={
            "sop_draft_id": fake_id,
            "action": "approved",
        },
    )
    assert res.status_code == 401, res.text
