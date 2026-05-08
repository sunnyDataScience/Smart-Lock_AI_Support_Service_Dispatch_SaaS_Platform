"""F-010 Reschedule / Delay quick-actions component tests。

涵蓋 12 案例（含 LINE Push fail-soft 行為）：
  1.  technician requestReschedule own order → 200
  2.  technician requestReschedule other tech's order → 403
  3.  admin approveReschedule (approve) → 200
  4.  requestReschedule with past datetime → 422
  5.  notifyDelay technician → 200 + LINE push attempted
  6.  notifyDelay non-LINE customer → notification_sent=false, channel=none
  7.  approveReschedule reject → status 不變 + 還原 scheduled_at
  8.  notifyDelay 缺 reason → 422
  9.  requestReschedule reason length 過長 → 422
  10. LINE push 失敗 → handler 不 fail（fail-soft，仍回 200）
  11. requestReschedule 工單不存在 → 404
  12. approveReschedule 由 technician 呼叫 → 403

LINE push 一律 monkeypatch `services.line_push_service.push_text` 以避免實際對外打 API。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio

from tests.conftest import (
    DEFAULT_TENANT_ID,
    _make_token,
)

pytestmark = pytest.mark.component


DEMO_TECH_USER_ID = "11111111-aaaa-bbbb-cccc-000000000001"
OTHER_TECH_USER_ID = "22222222-aaaa-bbbb-cccc-000000000002"


def _tech_headers(user_id: str = DEMO_TECH_USER_ID) -> dict:
    token = _make_token(user_id=user_id, role="technician")
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# Fixture: build user → conversation → problem_card → work_order chain
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def insert_work_order():
    """Factory fixture — returns wo_id with options for technician + LINE user.

    Always yields a callable; cleanup deletes everything created.
    """
    import core.db as db_module
    from core.db import _ensure_conn

    created: dict[str, list[str]] = {
        "wo": [],
        "pc": [],
        "conv": [],
        "user": [],
    }

    async def _factory(
        *,
        technician_id: str | None = DEMO_TECH_USER_ID,
        status: str = "accepted",
        line_user: bool = True,
        scheduled_at: str | None = None,
    ) -> str:
        await _ensure_conn()
        # Customer user — LINE or non-LINE
        cust_uid = str(uuid.uuid4())
        line_uid = (
            f"U{uuid.uuid4().hex}"  # LINE format: U + 32 hex
            if line_user
            else None
        )
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, line_user_id, display_name, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, 'line_user', TRUE)",
            (cust_uid, DEFAULT_TENANT_ID, line_uid, f"test-cust-{cust_uid[:6]}"),
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

        wo_id = str(uuid.uuid4())
        sched = scheduled_at or _future_iso(48)
        await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (id, problem_card_id, technician_id, status, customer_address, "
            "   priority, scheduled_at) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, '台北市中正區test', 'normal', "
            "        %s::timestamptz)",
            (wo_id, pc_id, technician_id, status, sched),
        )
        created["wo"].append(wo_id)
        return wo_id

    yield _factory

    await _ensure_conn()
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


@pytest.fixture
def mock_line_push(monkeypatch):
    """Patch line_push_service.push_text to avoid real LINE API calls.

    Returns a record-keeping list of call args; default behavior = success.
    """
    calls: list[dict[str, Any]] = []

    async def _fake_push(**kwargs):
        calls.append(kwargs)
        return True

    from services import line_push_service

    monkeypatch.setattr(line_push_service, "push_text", _fake_push)
    return calls


# ---------------------------------------------------------------------------
# Test cases (12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_01_technician_request_reschedule_own_order(
    client, insert_work_order, mock_line_push
):
    """Case 1: technician 改自己被指派的工單 → 200 + push attempted。"""
    wo_id = await insert_work_order(technician_id=DEMO_TECH_USER_ID)
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(),
        json={
            "new_scheduled_at": _future_iso(72),
            "reason": "客戶臨時要求改時間",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rescheduled"] is True
    assert body["channel"] == "line"
    assert body["notification_sent"] is True
    assert len(mock_line_push) == 1


@pytest.mark.asyncio
async def test_02_technician_request_reschedule_other_tech_order_returns_403(
    client, insert_work_order, mock_line_push
):
    """Case 2: technician 嘗試改別人的工單 → 403。"""
    wo_id = await insert_work_order(technician_id=OTHER_TECH_USER_ID)
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(DEMO_TECH_USER_ID),
        json={
            "new_scheduled_at": _future_iso(72),
            "reason": "搶單",
        },
    )
    assert res.status_code == 403, res.text
    assert mock_line_push == []


@pytest.mark.asyncio
async def test_03_admin_approve_reschedule(
    client, admin_headers, insert_work_order, mock_line_push
):
    """Case 3: admin approve → 200。"""
    wo_id = await insert_work_order()
    # 先建立一筆 reschedule_request 讓 service_report 有 [RESCHEDULE_REQUEST] tag
    await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(),
        json={"new_scheduled_at": _future_iso(72), "reason": "first"},
    )
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule/approve",
        headers=admin_headers,
        json={"decision": "approve", "comment": "ok"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["decision"] == "approve"
    assert body["reverted"] is False


@pytest.mark.asyncio
async def test_04_request_reschedule_past_datetime_returns_422(
    client, insert_work_order, mock_line_push
):
    """Case 4: new_scheduled_at 在過去 → 422。"""
    wo_id = await insert_work_order(technician_id=DEMO_TECH_USER_ID)
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(),
        json={
            "new_scheduled_at": _past_iso(),
            "reason": "穿越時空",
        },
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_05_notify_delay_technician_attempts_line_push(
    client, insert_work_order, mock_line_push
):
    """Case 5: notifyDelay technician → 200 + LINE push attempted。"""
    wo_id = await insert_work_order(technician_id=DEMO_TECH_USER_ID, status="in_progress")
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/notify-delay",
        headers=_tech_headers(),
        json={"delay_minutes": 30, "reason": "塞車"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["notification_sent"] is True
    assert body["channel"] == "line"
    assert len(mock_line_push) == 1
    assert "30 分鐘" in mock_line_push[0]["text"]


@pytest.mark.asyncio
async def test_06_notify_delay_non_line_customer(
    client, insert_work_order, mock_line_push
):
    """Case 6: 客戶非 LINE 用戶 → notification_sent=false / channel=none。"""
    wo_id = await insert_work_order(
        technician_id=DEMO_TECH_USER_ID,
        status="in_progress",
        line_user=False,
    )
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/notify-delay",
        headers=_tech_headers(),
        json={"delay_minutes": 15, "reason": "前一單延長"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["notification_sent"] is False
    assert body["channel"] == "none"
    # push_text 不應被呼叫（resolve 階段就 return None 了）
    assert mock_line_push == []


@pytest.mark.asyncio
async def test_07_approve_reschedule_reject_reverts_scheduled(
    client, admin_headers, insert_work_order, mock_line_push
):
    """Case 7: reject → 狀態不變 + scheduled_at 還原 + audit log。"""
    original = _future_iso(48)
    wo_id = await insert_work_order(
        technician_id=DEMO_TECH_USER_ID, scheduled_at=original
    )
    new_sched = _future_iso(96)
    await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(),
        json={"new_scheduled_at": new_sched, "reason": "first"},
    )
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule/approve",
        headers=admin_headers,
        json={"decision": "reject", "comment": "客戶反悔"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["decision"] == "reject"
    assert body["reverted"] is True
    # work_order.status 仍維持 accepted（reject 不切狀態）
    assert body["work_order"]["status"] == "accepted"


@pytest.mark.asyncio
async def test_08_notify_delay_missing_reason_returns_422(
    client, insert_work_order, mock_line_push
):
    """Case 8: 缺 reason → 422。"""
    wo_id = await insert_work_order(
        technician_id=DEMO_TECH_USER_ID, status="in_progress"
    )
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/notify-delay",
        headers=_tech_headers(),
        json={"delay_minutes": 30},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_09_request_reschedule_reason_too_long_returns_422(
    client, insert_work_order, mock_line_push
):
    """Case 9: reason > 500 字元 → 422。"""
    wo_id = await insert_work_order(technician_id=DEMO_TECH_USER_ID)
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule-request",
        headers=_tech_headers(),
        json={
            "new_scheduled_at": _future_iso(72),
            "reason": "X" * 501,
        },
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_10_line_push_failure_does_not_fail_handler(
    client, insert_work_order, monkeypatch
):
    """Case 10: LINE push raise / return False → handler 仍回 200（fail-soft）。"""
    from services import line_push_service

    async def _failing_push(**kwargs):
        return False  # simulate transient failure exhausted retries

    monkeypatch.setattr(line_push_service, "push_text", _failing_push)

    wo_id = await insert_work_order(
        technician_id=DEMO_TECH_USER_ID, status="in_progress"
    )
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/notify-delay",
        headers=_tech_headers(),
        json={"delay_minutes": 60, "reason": "斷電"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # channel 仍是 line（嘗試了），但 notification_sent=false
    assert body["channel"] == "line"
    assert body["notification_sent"] is False


@pytest.mark.asyncio
async def test_11_request_reschedule_unknown_work_order_returns_404(
    client, mock_line_push
):
    """Case 11: 工單不存在 → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/api/v1/work-orders/{fake_id}/reschedule-request",
        headers=_tech_headers(),
        json={"new_scheduled_at": _future_iso(72), "reason": "test"},
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_12_approve_reschedule_by_technician_returns_403(
    client, insert_work_order, mock_line_push
):
    """Case 12: technician 不能呼叫 approveReschedule → 403。"""
    wo_id = await insert_work_order(technician_id=DEMO_TECH_USER_ID)
    res = await client.post(
        f"/api/v1/work-orders/{wo_id}/reschedule/approve",
        headers=_tech_headers(),
        json={"decision": "approve"},
    )
    assert res.status_code == 403, res.text
