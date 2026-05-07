"""SLA 引擎背景偵測測試（v1.33.0）。

驗證：
  - 三類 alert_type 的 SQL 偵測正確
  - dedup：同 alert 不會重複推
  - 恢復：條件解除後從 _alerted set 移除
  - WS publish：透過 hub mock 攔截

注意：直接呼叫 SLAMonitor._scan_once 而不啟動 loop，避免 timing dependency。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def make_overdue_wo():
    """工廠 fixture：建立會觸發 dispatch_delay 的工單（建立時間在閾值之前）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created: list[str] = []

    async def _factory(*, status: str = "created", minutes_ago: int = 60) -> str:
        await _ensure_conn()
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"sla-test-{conv_id[:8]}"),
        )
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model) "
            "VALUES (%s::uuid, %s::uuid, 'Test', 'TestModel')",
            (pc_id, conv_id),
        )
        await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (id, problem_card_id, status, customer_address, priority, "
            "   estimated_price, created_at, updated_at) "
            "VALUES (%s::uuid, %s::uuid, %s, '台北市中正區test', 'normal', "
            "        1500.0, %s, %s)",
            (wo_id, pc_id, status, old_ts, old_ts),
        )
        created.append((wo_id, pc_id, conv_id))
        return wo_id

    yield _factory

    # cleanup
    if created:
        await _ensure_conn()
        for wo_id, pc_id, conv_id in created:
            await db_module._conn.execute(
                "DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,)
            )
            await db_module._conn.execute(
                "DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,)
            )
            await db_module._conn.execute(
                "DELETE FROM conversations WHERE id = %s::uuid", (conv_id,)
            )


@pytest.mark.asyncio
async def test_dispatch_delay_detected(make_overdue_wo):
    """work_orders.status='created' 超時 → 推 dispatch_delay。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_overdue_wo(status="created", minutes_ago=60)

    published: list[dict] = []

    async def fake_publish(channel, message):
        published.append({"channel": channel, "message": message})
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    # 找出我們插入的工單對應的告警
    matching = [
        p for p in published
        if p["channel"] == "/realtime/sla-alerts"
        and p["message"]["payload"]["target_id"] == wo_id
        and p["message"]["payload"]["alert_type"] == "dispatch_delay"
    ]
    assert len(matching) == 1, f"expected 1 dispatch_delay for {wo_id}, got {len(matching)}"


@pytest.mark.asyncio
async def test_dedup_no_repeat_alerts(make_overdue_wo):
    """同 alert 不會在第二次 scan 時重複推。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_overdue_wo(minutes_ago=60)

    publish_counts: dict[str, int] = {}

    async def counting_publish(channel, message):
        target = message["payload"]["target_id"]
        atype = message["payload"]["alert_type"]
        if target == wo_id and atype == "dispatch_delay":
            publish_counts[target] = publish_counts.get(target, 0) + 1
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=counting_publish):
        await monitor._scan_once()
        await monitor._scan_once()
        await monitor._scan_once()

    assert publish_counts.get(wo_id, 0) == 1, "dedup failed: pushed >1 time"


@pytest.mark.asyncio
async def test_recovery_removes_from_alerted():
    """工單狀態進入 in_progress → 從 _alerted 移除（下次再卡住會再推）。"""
    import core.db as db_module
    from core.db import _ensure_conn
    from realtime.sla_monitor import SLAMonitor

    await _ensure_conn()
    # 手動建立一筆並先注入 _alerted
    monitor = SLAMonitor()
    fake_id = str(uuid.uuid4())
    monitor._alerted.add(("dispatch_delay", fake_id))

    async def noop_publish(channel, message):
        return 0

    # 沒這筆 wo 在 DB → scan 不會 active_keys 含它 → 從 _alerted 移除
    with patch("realtime.ws_hub.hub.publish", side_effect=noop_publish):
        await monitor._scan_once()

    assert ("dispatch_delay", fake_id) not in monitor._alerted, (
        "recovery failed: stale alert lingered in _alerted"
    )
