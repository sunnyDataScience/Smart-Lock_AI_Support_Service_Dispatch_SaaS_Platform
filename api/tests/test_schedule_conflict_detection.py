"""Component tests for Flow 14 排班衝突偵測 — `_detect_schedule_conflict_and_publish`。

對應 commit `bd492059`：work_order_service 新增 helper 在 `assign_order` 後
best-effort 偵測同技師 ±2hr 內其他 active wo → INSERT work_order_events
event_type='schedule_conflict' + WS publish 至 /realtime/dispatch-queue。

測試矩陣（component；需真實 DB）：
  1. 同技師 + 同時段內有其他 active wo → 偵測到衝突，INSERT events + publish
  2. 同技師但時段差超過 2hr → 無衝突，無 publish
  3. 同時段但不同技師 → 無衝突
  4. 同技師同時段但另一 wo 是 completed → 無衝突（排除結案 wo）
  5. wo 無 scheduled_at → 無聲返回，無 publish
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def insert_wo_min():
    """最小 wo seed factory（不需 line_user / pc 完整鏈，本測試只關心 conflict 偵測）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {"wo": [], "pc": [], "conv": [], "user": [], "tech": []}

    async def _factory(
        *,
        technician_id: str | None,
        status: str = "assigned",
        scheduled_at: str | None = None,
    ) -> str:
        await _ensure_conn()
        cust_uid = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, display_name, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, %s, 'line_user', TRUE)",
            (cust_uid, DEFAULT_TENANT_ID, f"cust-{cust_uid[:6]}"),
        )
        created["user"].append(cust_uid)

        conv_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, cust_uid, f"sess-{conv_id[:8]}"),
        )
        created["conv"].append(conv_id)

        pc_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model) "
            "VALUES (%s::uuid, %s::uuid, 'TestBrand', 'TestModel')",
            (pc_id, conv_id),
        )
        created["pc"].append(pc_id)

        if technician_id and technician_id not in created["tech"]:
            await db_module._conn.execute(
                "INSERT INTO users (id, tenant_id, display_name, role, is_active) "
                "VALUES (%s::uuid, %s::uuid, %s, 'technician', TRUE) ON CONFLICT (id) DO NOTHING",
                (technician_id, DEFAULT_TENANT_ID, f"tech-{technician_id[:8]}"),
            )
            await db_module._conn.execute(
                "INSERT INTO technicians (id, tenant_id, name, phone) "
                "VALUES (%s::uuid, %s::uuid, %s, %s) ON CONFLICT (id) DO NOTHING",
                (technician_id, DEFAULT_TENANT_ID, f"tech-{technician_id[:8]}", "0900000000"),
            )
            created["tech"].append(technician_id)

        wo_id = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (id, tenant_id, problem_card_id, technician_id, status, customer_address, priority, scheduled_at) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, '台北市中正區', 'normal', %s::timestamptz)",
            (wo_id, DEFAULT_TENANT_ID, pc_id, technician_id, status, scheduled_at),
        )
        created["wo"].append(wo_id)
        return wo_id

    yield _factory

    await _ensure_conn()
    for table, ids in [
        ("work_order_events", []),  # cleanup happens via wo cascade if exists
        ("work_orders", created["wo"]),
        ("problem_cards", created["pc"]),
        ("conversations", created["conv"]),
        ("users", created["user"]),
    ]:
        if ids:
            await db_module._conn.execute(
                f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,),
            )
    # technicians cleanup
    if created["tech"]:
        await db_module._conn.execute(
            "DELETE FROM technicians WHERE id = ANY(%s::uuid[])", (created["tech"],),
        )


async def _count_conflict_events(wo_id: str) -> int:
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM work_order_events "
        "WHERE work_order_id = %s::uuid AND event_type = 'schedule_conflict'",
        (wo_id,),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 0


@pytest.mark.asyncio
async def test_detects_conflict_same_technician_within_window(insert_wo_min):
    """同技師 + 同時段內 → INSERT events + publish 被呼叫。"""
    from services import work_order_service

    tech_id = str(uuid.uuid4())
    base_time = datetime.now(timezone.utc) + timedelta(days=1)

    wo_old = await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=_iso(base_time),
    )
    wo_new = await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=_iso(base_time + timedelta(minutes=30)),
    )

    with patch("realtime.ws_hub.hub.publish", new=AsyncMock()) as mock_pub:
        await work_order_service._detect_schedule_conflict_and_publish(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_new, technician_id=tech_id,
        )

    assert mock_pub.await_count >= 1
    channel, message = mock_pub.await_args_list[0].args
    assert channel == "/realtime/dispatch-queue"
    assert message["type"] == "schedule_conflict_detected"
    assert message["payload"]["work_order_id"] == wo_new
    assert wo_old in message["payload"]["conflicting_wo_ids"]

    assert await _count_conflict_events(wo_new) == 1


@pytest.mark.asyncio
async def test_no_conflict_when_outside_window(insert_wo_min):
    """同技師但時段差 > 2hr → 無衝突。"""
    from services import work_order_service

    tech_id = str(uuid.uuid4())
    base_time = datetime.now(timezone.utc) + timedelta(days=1)

    await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=_iso(base_time),
    )
    wo_new = await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=_iso(base_time + timedelta(hours=5)),
    )

    with patch("realtime.ws_hub.hub.publish", new=AsyncMock()) as mock_pub:
        await work_order_service._detect_schedule_conflict_and_publish(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_new, technician_id=tech_id,
        )

    assert mock_pub.await_count == 0
    assert await _count_conflict_events(wo_new) == 0


@pytest.mark.asyncio
async def test_no_conflict_different_technicians(insert_wo_min):
    """同時段但不同技師 → 無衝突。"""
    from services import work_order_service

    tech_a = str(uuid.uuid4())
    tech_b = str(uuid.uuid4())
    base_time = datetime.now(timezone.utc) + timedelta(days=1)

    await insert_wo_min(
        technician_id=tech_a, status="assigned", scheduled_at=_iso(base_time),
    )
    wo_new = await insert_wo_min(
        technician_id=tech_b, status="assigned", scheduled_at=_iso(base_time + timedelta(minutes=10)),
    )

    with patch("realtime.ws_hub.hub.publish", new=AsyncMock()) as mock_pub:
        await work_order_service._detect_schedule_conflict_and_publish(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_new, technician_id=tech_b,
        )

    assert mock_pub.await_count == 0
    assert await _count_conflict_events(wo_new) == 0


@pytest.mark.asyncio
async def test_no_conflict_when_other_wo_completed(insert_wo_min):
    """同技師同時段但另一 wo 已 completed → 排除，無衝突。"""
    from services import work_order_service

    tech_id = str(uuid.uuid4())
    base_time = datetime.now(timezone.utc) + timedelta(days=1)

    await insert_wo_min(
        technician_id=tech_id, status="completed", scheduled_at=_iso(base_time),
    )
    wo_new = await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=_iso(base_time + timedelta(minutes=30)),
    )

    with patch("realtime.ws_hub.hub.publish", new=AsyncMock()) as mock_pub:
        await work_order_service._detect_schedule_conflict_and_publish(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_new, technician_id=tech_id,
        )

    assert mock_pub.await_count == 0
    assert await _count_conflict_events(wo_new) == 0


@pytest.mark.asyncio
async def test_no_publish_when_wo_has_no_scheduled_at(insert_wo_min):
    """wo.scheduled_at NULL → 無聲返回，無 publish。"""
    from services import work_order_service

    tech_id = str(uuid.uuid4())
    wo_id = await insert_wo_min(
        technician_id=tech_id, status="assigned", scheduled_at=None,
    )

    with patch("realtime.ws_hub.hub.publish", new=AsyncMock()) as mock_pub:
        await work_order_service._detect_schedule_conflict_and_publish(
            tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id, technician_id=tech_id,
        )

    assert mock_pub.await_count == 0
    assert await _count_conflict_events(wo_id) == 0
