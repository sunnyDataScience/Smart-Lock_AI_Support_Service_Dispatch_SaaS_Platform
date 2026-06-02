"""Component tests for M13 warranty-claims v2 tenant-scoped POST endpoint（CR-0003 P2 / FR-0015）。

測試矩陣：
  1. POST /tenants/{tenantId}/warranty-claims（with WO）→ 201 + WarrantyClaim envelope
  2. POST（without WO）→ 201
  3. Idempotency-Key replay → 200（冪等回放，同 key）
  4. business idempotency（同 work_order_id + claim_type，不同 Idempotency-Key）→ 200 + 同 id
  5. cross-tenant guard → 403 CROSS_TENANT_WRITE（path tenantId 與 JWT claim 不符）
  6. customer 不存在 → 404
  7. 跨 tenant customer → 404（tenant 偽裝 404）

路徑：POST /tenants/{tenantId}/warranty-claims
Service：warranty_service.create_warranty_claim（零業務邏輯重寫）

注意：本檔為 @pytest.mark.component，需 live DB（dev 環境 lock_AI_data）。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _path(tenant_id: str = DEFAULT_TENANT_ID) -> str:
    return f"/tenants/{tenant_id}/warranty-claims"


def _idem_headers(base_headers: dict) -> dict:
    """複製 base headers 並帶入 fresh Idempotency-Key。"""
    return {**base_headers, "Idempotency-Key": str(uuid.uuid4())}


def _make_other_tenant_headers(role: str = "admin") -> dict:
    """JWT claim 是 DEFAULT_TENANT 但 path 打 OTHER_TENANT → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=DEFAULT_TENANT_ID,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: customer + optional WO chain
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def insert_customer_and_wo(client):
    """建 customer（+ 可選 WO chain）；yield 工廠函式；測後清理。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "wo": [], "pc": [], "conv": [], "user": [],
    }

    async def _factory(
        *, tenant_id: str = DEFAULT_TENANT_ID, with_wo: bool = True,
    ) -> dict:
        await _ensure_conn()
        user_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, role) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user')",
            (user_id, tenant_id, f"U{user_id.replace('-', '')}"),
        )
        created["user"].append(user_id)

        wo_id = None
        if with_wo:
            conv_id = str(uuid.uuid4())
            pc_id = str(uuid.uuid4())
            wo_id = str(uuid.uuid4())
            await db_module._conn.execute(
                "INSERT INTO conversations (id, user_id, status, session_id) "
                "VALUES (%s::uuid, %s::uuid, 'active', %s)",
                (conv_id, user_id, f"v2-warr-{conv_id[:8]}"),
            )
            created["conv"].append(conv_id)
            await db_module._conn.execute(
                "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
                "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDR-1', 'confirmed')",
                (pc_id, conv_id),
            )
            created["pc"].append(pc_id)
            await db_module._conn.execute(
                "INSERT INTO work_orders (id, problem_card_id, status, customer_address, priority) "
                "VALUES (%s::uuid, %s::uuid, 'completed', '台北市中正區test-v2', 'normal')",
                (wo_id, pc_id),
            )
            created["wo"].append(wo_id)

        return {"user_id": user_id, "wo_id": wo_id}

    yield _factory

    # cleanup（依 FK 反序）
    from core.db import _ensure_conn as _ec
    await _ec()
    for u_id in created["user"]:
        await db_module._conn.execute(
            "DELETE FROM warranty_claims WHERE customer_id = %s::uuid",
            (u_id,),
        )
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


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_v2_happy_path_with_wo(
    client, admin_headers, insert_customer_and_wo,
):
    """POST /tenants/{tenantId}/warranty-claims（with WO）→ 201 + WarrantyClaim。"""
    chain = await insert_customer_and_wo(with_wo=True)
    res = await client.post(
        _path(),
        headers=_idem_headers(admin_headers),
        json={
            "customer_id": chain["user_id"],
            "work_order_id": chain["wo_id"],
            "device_brand": "Yale",
            "device_model": "YDR-1",
            "claim_type": "defective",
            "requested_by_role": "customer_service",
            "dispute_reason": "鎖頭故障 v2",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["customer_id"] == chain["user_id"]
    assert data["work_order_id"] == chain["wo_id"]
    assert data["status"] == "filed"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_v2_happy_path_without_wo(
    client, admin_headers, insert_customer_and_wo,
):
    """POST（without WO）→ 201，work_order_id is None。"""
    chain = await insert_customer_and_wo(with_wo=False)
    res = await client.post(
        _path(),
        headers=_idem_headers(admin_headers),
        json={
            "customer_id": chain["user_id"],
            "device_brand": "Samsung",
            "device_model": "SHP-1",
            "claim_type": "missing_parts",
            "requested_by_role": "customer_via_line",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["work_order_id"] is None
    assert data["customer_id"] == chain["user_id"]


@pytest.mark.asyncio
async def test_create_v2_idempotency_key_replay(
    client, admin_headers, insert_customer_and_wo,
):
    """同一 Idempotency-Key 重送 → 200 冪等回放，回傳相同 payload。"""
    chain = await insert_customer_and_wo(with_wo=False)
    idem_key = str(uuid.uuid4())
    headers = {**admin_headers, "Idempotency-Key": idem_key}
    body = {
        "customer_id": chain["user_id"],
        "device_brand": "Dormakaba",
        "device_model": "AS701",
        "claim_type": "malfunction",
        "requested_by_role": "customer_service",
    }

    res1 = await client.post(_path(), headers=headers, json=body)
    assert res1.status_code == 201, res1.text
    claim_id_1 = res1.json()["data"]["id"]

    # 相同 key → 冪等回放（200）
    res2 = await client.post(_path(), headers=headers, json=body)
    assert res2.status_code in (200, 201), res2.text
    assert res2.json()["data"]["id"] == claim_id_1


@pytest.mark.asyncio
async def test_create_v2_business_idempotency_same_claim_type(
    client, admin_headers, insert_customer_and_wo,
):
    """同 work_order_id + claim_type，不同 Idempotency-Key → 200 + 同 id（業務冪等）。"""
    chain = await insert_customer_and_wo(with_wo=True)
    body = {
        "customer_id": chain["user_id"],
        "work_order_id": chain["wo_id"],
        "device_brand": "X",
        "device_model": "Y",
        "claim_type": "premature_failure",
        "requested_by_role": "customer_service",
    }

    res1 = await client.post(
        _path(), headers=_idem_headers(admin_headers), json=body
    )
    assert res1.status_code == 201, res1.text
    cid1 = res1.json()["data"]["id"]

    res2 = await client.post(
        _path(), headers=_idem_headers(admin_headers), json=body
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["data"]["id"] == cid1


@pytest.mark.asyncio
async def test_create_v2_cross_tenant_403(
    client, insert_customer_and_wo,
):
    """path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_WRITE。"""
    chain = await insert_customer_and_wo(with_wo=False)
    headers = _idem_headers(_make_other_tenant_headers())
    res = await client.post(
        _path(OTHER_TENANT_ID),  # path 打 OTHER_TENANT
        headers=headers,
        json={
            "customer_id": chain["user_id"],
            "device_brand": "X",
            "device_model": "Y",
            "claim_type": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 403, res.text
    assert res.json()["error_code"] == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_create_v2_customer_not_found(client, admin_headers):
    """不存在的 customer_id → 404。"""
    res = await client.post(
        _path(),
        headers=_idem_headers(admin_headers),
        json={
            "customer_id": str(uuid.uuid4()),
            "device_brand": "X",
            "device_model": "Y",
            "claim_type": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_create_v2_cross_tenant_customer_404(
    client, admin_headers, insert_customer_and_wo,
):
    """屬於其他 tenant 的 customer → 404（tenant 偽裝）。"""
    chain = await insert_customer_and_wo(
        with_wo=False, tenant_id=OTHER_TENANT_ID
    )
    res = await client.post(
        _path(),  # DEFAULT_TENANT path
        headers=_idem_headers(admin_headers),
        json={
            "customer_id": chain["user_id"],  # 屬於 OTHER_TENANT
            "device_brand": "X",
            "device_model": "Y",
            "claim_type": "other",
            "requested_by_role": "customer_service",
        },
    )
    assert res.status_code == 404, res.text
