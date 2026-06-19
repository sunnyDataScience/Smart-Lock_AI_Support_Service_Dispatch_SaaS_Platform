"""CR-0041 M15 異常框架測試（BR-M15-01 return_path / BR-M15-03 high-risk pause）。

component（真 DB，需 migration 049）：exception lifecycle + high_risk_hold 擋派工/完工。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import exception_service as es
from services import work_order_service as wos

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _seed_wo(wo_id: str, status: str = "created") -> None:
    # tenant_id 必填：complete_order 走 _fetch_status_for_update 會依 tenant 過濾
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, tenant_id, status, customer_address, brand, model, problem_type) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'Yale', 'YDM-4109', '電池故障')",
        (wo_id, DEFAULT_TENANT_ID, status, "新北市板橋區文化路1號"),
    )


async def _cleanup(wo_id: str) -> None:
    await db_module._conn.execute("DELETE FROM saas.exception_case WHERE work_order_id = %s::uuid", (wo_id,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,))


async def _hold(wo_id: str) -> bool:
    cur = await db_module._conn.execute("SELECT high_risk_hold FROM work_orders WHERE id = %s::uuid", (wo_id,))
    row = await cur.fetchone()
    return bool(row and row[0])


pytestmark_component = pytest.mark.component


@pytest.mark.component
@pytest.mark.asyncio
async def test_open_invalid_type_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await es.open_exception(tenant_id=DEFAULT_TENANT_ID, exception_type="bogus")
    assert ei.value.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_open_medium_no_hold():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id)
    try:
        exc = await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="material_shortage",
            work_order_id=wo_id, severity="medium",
        )
        assert exc["status"] == "open"
        assert await _hold(wo_id) is False  # medium 不暫停
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_high_severity_sets_hold_and_blocks_dispatch_and_complete():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id, status="in_progress")
    try:
        await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="appearance_refused",
            work_order_id=wo_id, severity="high", description="安全風險",
        )
        assert await _hold(wo_id) is True  # BR-M15-03 high → hold

        # 派工/完工共用的 high_risk_hold gate 直接驗（assign_order/complete_order 皆呼此）
        with pytest.raises(ApiError) as ei:
            await wos._assert_not_high_risk_hold(wo_id)
        assert ei.value.error_code == "HIGH_RISK_HOLD"
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_clears_hold_and_records_return_path():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id, status="in_progress")
    try:
        exc = await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="quality_complaint",
            work_order_id=wo_id, severity="critical",
        )
        assert await _hold(wo_id) is True
        resolved = await es.resolve_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_id=exc["id"],
            return_path="reschedule", resolution="改期重做",
        )
        assert resolved["status"] == "resolved"
        assert resolved["return_path"] == "reschedule"
        assert await _hold(wo_id) is False  # 無其他 open high-risk → 解除 hold
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_invalid_return_path_422():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id)
    try:
        exc = await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="other", work_order_id=wo_id,
        )
        with pytest.raises(ApiError) as ei:
            await es.resolve_exception(
                tenant_id=DEFAULT_TENANT_ID, exception_id=exc["id"], return_path="bogus",
            )
        assert ei.value.status_code == 422
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_escalate_and_list():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id)
    try:
        exc = await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="no_show", work_order_id=wo_id,
        )
        esc = await es.escalate_exception(tenant_id=DEFAULT_TENANT_ID, exception_id=exc["id"])
        assert esc["status"] == "escalated"
        listing = await es.list_exceptions(tenant_id=DEFAULT_TENANT_ID, status="escalated")
        assert any(it["id"] == exc["id"] for it in listing["items"])
    finally:
        await _cleanup(wo_id)
