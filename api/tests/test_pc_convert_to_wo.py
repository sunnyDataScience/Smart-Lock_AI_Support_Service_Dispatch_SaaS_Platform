"""F-002 客服審 PC → 開 WO（convertToWorkOrder）整合測試。

測試矩陣：
  1. Happy path：confirmed PC + user.address 存在 → 201 + new WO（priority 對齊 urgency）
  2. Idempotency：同 PC 二次呼叫 → 200 + 同 WO id
  3. State conflict：draft PC → 409 STATE_CONFLICT
  4. State conflict：resolved PC → 409 STATE_CONFLICT
  5. Missing address：user.address NULL + body 無 customer_address → 422
  6. Address override：body.customer_address 提供 → 採用 body 值（不取 user.address）
  7. Tenant isolation：跨 tenant 取 PC → 404
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def insert_pc_chain(client):
    """工廠 fixture：建立 user → conversation → problem_card chain。

    Args:
      pc_status: 'incomplete' / 'confirmed' / 'resolved'
      user_address: users.address 欄位值（None 表示不設）
      tenant_id: 用於 multi-tenant 隔離測試
      urgency: PC.urgency 欄位（low / medium / high）

    Returns:
      dict with keys: pc_id, user_id, conv_id
    """
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"pc": [], "conv": [], "wo": [], "user": []}

    async def _factory(
        *,
        pc_status: str = "confirmed",
        user_address: str | None = "新北市板橋區test 1 號",
        user_name: str = "張三",
        user_phone: str = "0900-000-001",
        tenant_id: str = DEFAULT_TENANT_ID,
        urgency: str = "medium",
    ) -> dict:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())

        await db_module._conn.execute(
            "INSERT INTO users "
            "  (id, tenant_id, line_user_id, display_name, address, phone, role) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, 'line_user')",
            (
                user_id,
                tenant_id,
                f"U{user_id.replace('-', '')}",
                user_name,
                user_address,
                user_phone,
            ),
        )
        created["user"].append(user_id)

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, user_id, f"test-pc-conv-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)

        await db_module._conn.execute(
            "INSERT INTO problem_cards "
            "  (id, conversation_id, brand, model, symptom, status, urgency) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)",
            (pc_id, conv_id, "TestBrand", "TestModel", "test symptom",
             pc_status, urgency),
        )
        created["pc"].append(pc_id)

        return {"pc_id": pc_id, "user_id": user_id, "conv_id": conv_id}

    yield _factory

    # cleanup（FK 反序）
    await _ensure_conn()
    # 撈本次建立的 PC 對應 WO 一併刪除
    for pc_id in created["pc"]:
        cur = await db_module._conn.execute(
            "SELECT id FROM work_orders WHERE problem_card_id = %s::uuid",
            (pc_id,),
        )
        rows = await cur.fetchall()
        for row in rows:
            created["wo"].append(str(row[0]))
    for table, ids in [
        ("work_orders", created["wo"]),
        ("problem_cards", created["pc"]),
        ("conversations", created["conv"]),
        ("users", created["user"]),
    ]:
        if ids:
            await db_module._conn.execute(
                f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,)
            )


# ============================================================================
# 1. Happy path
# ============================================================================
@pytest.mark.asyncio
async def test_convert_happy_path(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(
        pc_status="confirmed", urgency="high",
    )
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    wo = body["data"]
    assert wo["problem_card_id"] == chain["pc_id"]
    # urgency=high → priority=high → mapped back to API urgency=high
    assert wo["urgency"] == "high"
    # status: created → API mapped to "inquiring"（依 _DB_STATUS_TO_API）
    assert wo["status"] == "inquiring"


# ============================================================================
# 2. Idempotency：同 PC 二次呼叫 → 200 + 同 WO id
# ============================================================================
@pytest.mark.asyncio
async def test_convert_idempotent(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(pc_status="confirmed")
    res1 = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res1.status_code == 201
    wo_id_1 = res1.json()["data"]["id"]

    # 第二次呼叫（不同 idempotency key）— 業務層 idempotency 應回既存 WO
    res2 = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == wo_id_1


# ============================================================================
# 3. State conflict：draft PC → 409
# ============================================================================
@pytest.mark.asyncio
async def test_convert_draft_rejected(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(pc_status="incomplete")
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "STATE_CONFLICT"


# ============================================================================
# 4. State conflict：resolved PC → 409
# ============================================================================
@pytest.mark.asyncio
async def test_convert_resolved_rejected(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(pc_status="resolved")
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 409


# ============================================================================
# 5. Missing address：user.address NULL + body 無 customer_address → 422
# ============================================================================
@pytest.mark.asyncio
async def test_convert_missing_address_422(
    client, admin_headers, insert_pc_chain,
):
    chain = await insert_pc_chain(
        pc_status="confirmed", user_address=None,
    )
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# 6. Address override：body.customer_address 提供 → 採用 body 值
# ============================================================================
@pytest.mark.asyncio
async def test_convert_address_override(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(
        pc_status="confirmed", user_address="新北市板橋區舊地址 1 號",
    )
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"customer_address": "台北市信義區覆寫地址 99 號"},
    )
    assert res.status_code == 201
    wo = res.json()["data"]
    # WO.address 序列化使用 customer_address 原文（district 解析自前綴）
    assert wo["address"] == "台北市信義區覆寫地址 99 號"
    assert wo["district"].startswith("台北市信義區")


# ============================================================================
# 7. Tenant isolation：跨 tenant 取 PC → 404
# ============================================================================
@pytest.mark.asyncio
async def test_convert_cross_tenant_404(client, admin_headers, insert_pc_chain):
    other_tenant = "00000000-0000-0000-0000-000000000099"
    chain = await insert_pc_chain(
        pc_status="confirmed", tenant_id=other_tenant,
    )
    # admin_headers 走 DEFAULT_TENANT_ID，無法看到 other_tenant 的 PC
    res = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res.status_code == 404
