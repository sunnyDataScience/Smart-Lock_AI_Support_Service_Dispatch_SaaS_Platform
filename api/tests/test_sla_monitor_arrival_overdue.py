"""F-016 SLA 紅色警報 — arrival_overdue 偵測測試（v1.34.0）。

對應：
  - docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md F-110 (4 scenarios)
  - PM Q5=B 拍板：Soft SLA — 警報 + 升 Ops Manager + 寫稽核，無賠償 / 沖銷 / 自動退款

驗證：
  1. 已 assigned 工單 + scheduled_at < NOW - 2hr - buffer + 未 started → 觸發
  2. 已 assigned 工單 + scheduled_at = NOW - 1hr → 不觸發
  3. 已 completed 工單（不論 scheduled_at）→ 不觸發
  4. dedup：同一工單連續 scan 不重複 publish
  5. recovery：技師到場 (started_at IS NOT NULL) 後從 _alerted 移除
  6. **no compensation logic**：publish payload 嚴禁含 compensation / refund / voucher
  7. WS envelope 結構符合 AsyncAPI spec（type/payload + alert_type/severity/escalated_to）
  8. audit log 寫入 escalation 事件 + payload.policy="Q5=B Soft SLA"
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio

from tests.conftest import ADMIN_USER_ID, audit_privileged_exec

pytestmark = pytest.mark.component


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def make_work_order():
    """工廠 fixture：建立可控制 status / scheduled_at / started_at 的工單。

    回傳 wo_id；自動 cleanup conv → pc → wo（CASCADE 安全）。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    created: list[tuple[str, str, str]] = []

    async def _factory(
        *,
        status: str = "assigned",
        scheduled_minutes_ago: int | None = 130,
        started: bool = False,
    ) -> str:
        await _ensure_conn()
        conv_id = str(uuid.uuid4())
        pc_id = str(uuid.uuid4())
        wo_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        scheduled_at = (
            now - timedelta(minutes=scheduled_minutes_ago)
            if scheduled_minutes_ago is not None
            else None
        )
        started_at = now - timedelta(minutes=5) if started else None

        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, status, session_id) "
            "VALUES (%s::uuid, %s::uuid, 'active', %s)",
            (conv_id, ADMIN_USER_ID, f"sla-arr-{conv_id[:8]}"),
        )
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model) "
            "VALUES (%s::uuid, %s::uuid, 'Test', 'TestModel')",
            (pc_id, conv_id),
        )
        await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (id, problem_card_id, status, customer_address, priority, "
            "   estimated_price, scheduled_at, started_at, created_at, updated_at) "
            "VALUES (%s::uuid, %s::uuid, %s, '台北市信義區test', 'normal', "
            "        1500.0, %s, %s, NOW(), NOW())",
            (wo_id, pc_id, status, scheduled_at, started_at),
        )
        created.append((wo_id, pc_id, conv_id))
        return wo_id

    yield _factory

    if created:
        import core.db as db_module
        from core.db import _ensure_conn

        await _ensure_conn()
        for wo_id, pc_id, conv_id in created:
            await audit_privileged_exec(
                "DELETE FROM audit_events WHERE target_id = %s::uuid",
                (wo_id,),
            )
            await db_module._conn.execute(
                "DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,)
            )
            await db_module._conn.execute(
                "DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,)
            )
            await db_module._conn.execute(
                "DELETE FROM conversations WHERE id = %s::uuid", (conv_id,)
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _arrival_alerts_for(published: list[dict], wo_id: str) -> list[dict]:
    return [
        p
        for p in published
        if p["channel"] == "/realtime/sla-alerts"
        and p["message"].get("payload", {}).get("alert_type") == "arrival_overdue"
        and p["message"]["payload"].get("target_id") == wo_id
    ]


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_arrival_overdue_detected(make_work_order):
    """assigned + scheduled_at = NOW - 130 min + 未 started → 觸發 arrival_overdue。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    published: list[dict] = []

    async def fake_publish(channel, message):
        published.append({"channel": channel, "message": message})
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    matching = _arrival_alerts_for(published, wo_id)
    assert len(matching) == 1, (
        f"expected 1 arrival_overdue for {wo_id}, got {len(matching)}"
    )


@pytest.mark.asyncio
async def test_arrival_within_threshold_no_trigger(make_work_order):
    """assigned + scheduled_at = NOW - 60 min → 不觸發（120 分閾值未到）。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=60, started=False
    )

    published: list[dict] = []

    async def fake_publish(channel, message):
        published.append({"channel": channel, "message": message})
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    assert _arrival_alerts_for(published, wo_id) == []


@pytest.mark.asyncio
async def test_completed_wo_no_trigger(make_work_order):
    """工單 completed → 不論 scheduled 多久都不觸發 arrival_overdue。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="completed", scheduled_minutes_ago=300, started=True
    )

    published: list[dict] = []

    async def fake_publish(channel, message):
        published.append({"channel": channel, "message": message})
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    assert _arrival_alerts_for(published, wo_id) == []


@pytest.mark.asyncio
async def test_dedup_no_repeat_arrival_alerts(make_work_order):
    """同 wo 連續多次 scan 不重複 publish arrival_overdue。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    counts: dict[str, int] = {}

    async def counting_publish(channel, message):
        target = message.get("payload", {}).get("target_id")
        atype = message.get("payload", {}).get("alert_type")
        if target == wo_id and atype == "arrival_overdue":
            counts[target] = counts.get(target, 0) + 1
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=counting_publish):
        await monitor._scan_once()
        await monitor._scan_once()
        await monitor._scan_once()

    assert counts.get(wo_id, 0) == 1, "dedup failed for arrival_overdue"


@pytest.mark.asyncio
async def test_recovery_after_check_in(make_work_order):
    """技師到場後（started_at 設值）→ 從 _alerted 移除（下次再卡會再推）。"""
    import core.db as db_module
    from core.db import _ensure_conn
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    async def noop_publish(channel, message):
        return 0

    monitor = SLAMonitor()

    # 第一次 scan：應該推 + 加入 _alerted
    with patch("realtime.ws_hub.hub.publish", side_effect=noop_publish):
        await monitor._scan_once()
    assert ("arrival_overdue", wo_id) in monitor._alerted

    # 模擬技師 check-in
    await _ensure_conn()
    await db_module._conn.execute(
        "UPDATE work_orders SET started_at = NOW(), status = 'in_progress' "
        "WHERE id = %s::uuid",
        (wo_id,),
    )

    # 第二次 scan：應從 _alerted 移除（recovery）
    with patch("realtime.ws_hub.hub.publish", side_effect=noop_publish):
        await monitor._scan_once()
    assert ("arrival_overdue", wo_id) not in monitor._alerted, (
        "recovery failed: stale arrival_overdue lingered after check-in"
    )


@pytest.mark.asyncio
async def test_no_compensation_in_payload(make_work_order):
    """payload 嚴禁出現 compensation / refund / voucher 字段（PM Q5=B Soft SLA）。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    captured: list[dict] = []

    async def fake_publish(channel, message):
        captured.append(message)
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    arrival_msgs = [
        m
        for m in captured
        if m.get("payload", {}).get("alert_type") == "arrival_overdue"
        and m["payload"].get("target_id") == wo_id
    ]
    assert len(arrival_msgs) == 1
    payload = arrival_msgs[0]["payload"]

    # 鐵律：嚴禁這些欄位出現在 publish payload
    forbidden = {
        "compensation",
        "compensation_amount",
        "refund",
        "refund_id",
        "voucher",
        "voucher_id",
        "auto_refund_triggered",
        "settlement_offset",
    }
    payload_str = json.dumps(payload, ensure_ascii=False).lower()
    for f in forbidden:
        assert f not in payload, (
            f"forbidden compensation field '{f}' leaked into arrival_overdue payload "
            f"(violates Q5=B Soft SLA)"
        )
    # double-check：payload JSON 整體不含 refund/賠償 字串
    assert "refund" not in payload_str
    assert "compensation" not in payload_str


@pytest.mark.asyncio
async def test_ws_envelope_structure(make_work_order):
    """WS envelope 結構符合 AsyncAPI spec：channel + type + payload + 必要 alert 欄位。"""
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    captured: list[dict] = []

    async def fake_publish(channel, message):
        captured.append({"channel": channel, "message": message})
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    matching = [
        c
        for c in captured
        if c["channel"] == "/realtime/sla-alerts"
        and c["message"].get("payload", {}).get("target_id") == wo_id
        and c["message"]["payload"].get("alert_type") == "arrival_overdue"
    ]
    assert len(matching) == 1, "expected exactly 1 arrival_overdue message"

    msg = matching[0]["message"]
    # envelope
    assert msg["type"] == "sla.alert"
    assert "payload" in msg
    payload = msg["payload"]
    # SlaAlertData required + F-016 specific
    assert payload["alert_type"] == "arrival_overdue"
    assert payload["target_id"] == wo_id
    assert payload["severity"] == "red"
    assert payload["escalated_to"] == "ops_manager"
    assert isinstance(payload.get("threshold_minutes"), int)
    assert payload["threshold_minutes"] >= 1


@pytest.mark.asyncio
async def test_audit_log_recorded_for_arrival_overdue(make_work_order):
    """arrival_overdue 觸發後應寫入 audit_events（escalation 類型 + Q5=B 標記）。"""
    import core.db as db_module
    from core.db import _ensure_conn
    from realtime.sla_monitor import SLAMonitor

    wo_id = await make_work_order(
        status="assigned", scheduled_minutes_ago=130, started=False
    )

    async def fake_publish(channel, message):
        return 1

    monitor = SLAMonitor()
    with patch("realtime.ws_hub.hub.publish", side_effect=fake_publish):
        await monitor._scan_once()

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT event_type, action, payload "
        "FROM audit_events "
        "WHERE target_id = %s::uuid AND action = 'sla.arrival_overdue'",
        (wo_id,),
    )
    rows = await cur.fetchall()
    assert len(rows) == 1, (
        f"expected 1 audit_events row for {wo_id} action=sla.arrival_overdue, got {len(rows)}"
    )
    event_type, action, payload = rows[0]
    assert event_type == "escalation"
    assert action == "sla.arrival_overdue"
    assert payload is not None
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload.get("policy") == "Q5=B Soft SLA"
    assert payload.get("compensation") == "none"
    assert payload.get("auto_refund") is False
    assert payload.get("escalated_to") == "ops_manager"
