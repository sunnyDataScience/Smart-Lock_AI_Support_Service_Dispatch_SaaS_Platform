"""CR-0166 R1-4：技師品牌授權 grant/revoke live API（原僅 seed）。

單庫 fallback（scratch）：require_tech_conn 回同一連線；本表與 saas.technician_lifecycle_event
同庫可測。
"""

from __future__ import annotations

import pytest

import core.db as db_module
from core.errors import ApiError
from services import technician_brand_auth_service as svc
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02"  # 陳師傅（seed）
BRAND = "CR0166TestBrand"


async def _cleanup() -> None:
    await db_module._ensure_conn()
    conn = await db_module.require_tech_conn()
    await conn.execute(
        "DELETE FROM technician_brand_authorization WHERE technician_id=%s::uuid AND brand=%s",
        (SEED_TECH, BRAND))
    await conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid "
        "AND event_type IN ('brand_auth_granted','brand_auth_revoked')",
        (SEED_TECH,))


@pytest.mark.asyncio
async def test_grant_then_revoke():
    await db_module._ensure_conn()
    try:
        # grant（首次）
        r = await svc.grant_brand_authorization(
            tenant_id=TID, technician_id=SEED_TECH, brand=BRAND,
            actor_user_id="c782bcfe-89bb-40b3-94b3-8c73d7bd0961", reason="測試授權")
        assert r["brand"] == BRAND and r["authorized"] is True

        # grant 再次（冪等 upsert，仍 authorized）
        r2 = await svc.grant_brand_authorization(
            tenant_id=TID, technician_id=SEED_TECH, brand=BRAND,
            actor_user_id="c782bcfe-89bb-40b3-94b3-8c73d7bd0961")
        assert r2["authorized"] is True

        # list 含此品牌
        items = await svc.list_brand_authorizations(tenant_id=TID, technician_id=SEED_TECH)
        assert any(x["brand"] == BRAND and x["authorized"] for x in items)

        # revoke（軟撤）
        rv = await svc.revoke_brand_authorization(
            tenant_id=TID, technician_id=SEED_TECH, brand=BRAND,
            actor_user_id="c782bcfe-89bb-40b3-94b3-8c73d7bd0961", reason="測試撤證")
        assert rv["authorized"] is False

        # audit 事件寫入（grant + revoke）
        conn = await db_module.require_tech_conn()
        cur = await conn.execute(
            "SELECT event_type FROM saas.technician_lifecycle_event "
            "WHERE technician_id=%s::uuid AND event_type IN "
            "('brand_auth_granted','brand_auth_revoked') ORDER BY created_at",
            (SEED_TECH,))
        events = {r[0] for r in await cur.fetchall()}
        assert "brand_auth_granted" in events and "brand_auth_revoked" in events
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_revoke_nonexistent_404():
    await db_module._ensure_conn()
    with pytest.raises(ApiError) as e:
        await svc.revoke_brand_authorization(
            tenant_id=TID, technician_id=SEED_TECH, brand="NeverGrantedBrand")
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_grant_empty_brand_422():
    await db_module._ensure_conn()
    with pytest.raises(ApiError) as e:
        await svc.grant_brand_authorization(
            tenant_id=TID, technician_id=SEED_TECH, brand="  ")
    assert e.value.error_code == "VALIDATION_ERROR"
