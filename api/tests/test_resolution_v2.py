"""Resolution v2 — tenant-scoped 解決方案引擎建議（Track B S6 / CR-0004 §8 C4）。

POST /tenants/{tenantId}/problem-cards/{problemCardId}:resolve-suggest
  → 包 resolution_service.resolve_problem（L1 faq / L2 rag / L3 escalation，純 DB）。

component（需 live DB）：覆蓋 escalation happy path、404 missing card、cross-tenant 403。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID

pytestmark = pytest.mark.component

_OTHER_TENANT = "00000000-0000-0000-0000-0000000000ff"


async def _insert_problem_card(
    *,
    brand: str = "TestBrand",
    model: str = "TestModel",
    symptoms: str = '["門打不開"]',
    status: str = "confirmed",
) -> tuple[str, str]:
    """建 conversation（user=seeded admin，tenant=DEFAULT）+ problem_card，回 (pc_id, conv_id)。

    get_card 經 problem_cards→conversations→users(tenant_id) JOIN 過濾租戶，故須完整鏈。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    conv_id = str(uuid.uuid4())
    pc_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')",
        (conv_id, ADMIN_USER_ID, f"s6-{conv_id[:8]}"),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, symptoms, status, created_at) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, NOW())",
        (pc_id, conv_id, brand, model, symptoms, status),
    )
    return pc_id, conv_id


async def _cleanup(pc_id: str, conv_id: str) -> None:
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (conv_id,))


@pytest_asyncio.fixture
async def problem_card_id():
    pc_id, conv_id = await _insert_problem_card()
    yield pc_id
    await _cleanup(pc_id, conv_id)


def _idem(headers: dict) -> dict:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def test_resolve_suggest_escalation(client, admin_headers, problem_card_id):
    """無相符案例 → escalation layer（純 DB 引擎，不打 LLM）。"""
    r = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards/{problem_card_id}:resolve-suggest",
        headers=_idem(admin_headers),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["layer"] in (
        "faq_match",
        "knowledge_base_rag",
        "llm_generation",
        "escalation",
    )
    assert isinstance(body["answer"], str) and len(body["answer"]) > 0


async def test_resolve_suggest_404_missing_card(client, admin_headers):
    """不存在的 problem card → 404。"""
    missing = str(uuid.uuid4())
    r = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards/{missing}:resolve-suggest",
        headers=_idem(admin_headers),
    )
    assert r.status_code == 404, r.text


async def test_resolve_suggest_cross_tenant_403(client, admin_headers, problem_card_id):
    """path tenantId 與 token tenant 不符 → 403。"""
    r = await client.post(
        f"/tenants/{_OTHER_TENANT}/problem-cards/{problem_card_id}:resolve-suggest",
        headers=_idem(admin_headers),
    )
    assert r.status_code == 403, r.text
