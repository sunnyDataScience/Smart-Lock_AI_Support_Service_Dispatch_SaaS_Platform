"""CR-0042 Alpha Exit 收尾測試（ProblemCard completeness gate #1 + 客戶 phone 去重 #6）。

component（真 DB，需 migration 051）：
- assert_completeness：足量/不足/主管 override/非管理角色 override 無效。
- create_customer：phone 重複 → 422 DUPLICATE_CUSTOMER。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import customer_service as cs
from services import problem_card_service as pcs

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _insert_pc(pc_id: str, *, brand="Yale", model="YDM-4109",
                     symptoms='["電池故障"]', urgency="normal") -> None:
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, brand, model, symptoms, urgency, status) "
        "VALUES (%s::uuid, %s, %s, %s::jsonb, %s, 'incomplete')",
        (pc_id, brand, model, symptoms, urgency),
    )


async def _del_pc(pc_id: str) -> None:
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,))


# ── completeness gate ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_completeness_full_passes():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await _insert_pc(pc)
    try:
        r = await pcs.assert_completeness(
            tenant_id=TID, pc_id=pc, customer_address="台北市信義區忠孝東路1號"
        )
        assert r["score"] >= 0.8
        assert r["overridden"] is False
        assert r["missing"] == []
    finally:
        await _del_pc(pc)


@pytest.mark.asyncio
async def test_completeness_missing_two_blocked_422():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await _insert_pc(pc, model="")  # 缺 model + 缺 address → 0.6 < 0.8
    try:
        with pytest.raises(ApiError) as ei:
            await pcs.assert_completeness(tenant_id=TID, pc_id=pc, customer_address=None)
        assert ei.value.status_code == 422
        assert ei.value.error_code == "INCOMPLETE_PROBLEM_CARD"
    finally:
        await _del_pc(pc)


@pytest.mark.asyncio
async def test_completeness_override_by_admin_passes():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await _insert_pc(pc, model="")
    try:
        r = await pcs.assert_completeness(
            tenant_id=TID, pc_id=pc, customer_address=None,
            actor_role="admin", override_reason="急件先轉，後補型號",
        )
        assert r["overridden"] is True
    finally:
        await _del_pc(pc)


@pytest.mark.asyncio
async def test_completeness_override_by_technician_ignored_422():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await _insert_pc(pc, model="")
    try:
        with pytest.raises(ApiError) as ei:
            await pcs.assert_completeness(
                tenant_id=TID, pc_id=pc, customer_address=None,
                actor_role="technician", override_reason="x",
            )
        assert ei.value.error_code == "INCOMPLETE_PROBLEM_CARD"  # 非管理角色 override 無效
    finally:
        await _del_pc(pc)


# ── phone 去重 ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_phone_dedup_422():
    assert await db_module._ensure_conn()
    phone = "09" + str(uuid.uuid4().int)[-8:]
    c1 = await cs.create_customer(tenant_id=TID, payload={"display_name": "客A", "phone": phone})
    try:
        with pytest.raises(ApiError) as ei:
            await cs.create_customer(tenant_id=TID, payload={"display_name": "客B", "phone": phone})
        assert ei.value.status_code == 422
        assert ei.value.error_code == "DUPLICATE_CUSTOMER"
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE phone = %s", (phone,))


@pytest.mark.asyncio
async def test_different_phone_ok():
    assert await db_module._ensure_conn()
    p1 = "09" + str(uuid.uuid4().int)[-8:]
    p2 = "09" + str(uuid.uuid4().int)[-8:]
    try:
        await cs.create_customer(tenant_id=TID, payload={"display_name": "客C", "phone": p1})
        await cs.create_customer(tenant_id=TID, payload={"display_name": "客D", "phone": p2})
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE phone IN (%s, %s)", (p1, p2))
