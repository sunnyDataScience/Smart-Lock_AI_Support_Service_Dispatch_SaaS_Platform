"""F-004 手動派工 BDD/component 測試。

涵蓋場景（PM 拍板）：
  - Q1=A: dispatcher 為獨立角色，可呼叫 assignWorkOrder / assignDispatch。
  - Q6=A: customer_service 可繞過自動派工，但繞過時必須寫 audit log。

覆蓋矩陣：
  1. dispatcher 呼叫 assignWorkOrder → 200
  2. customer_service 呼叫 assignWorkOrder（繞過）→ 200 + audit log 寫入
  3. technician 呼叫 assignWorkOrder → 403
  4. dispatcher 呼叫 assignDispatch → 200
  5. customer_service 繞過後 audit log payload 內容驗證
  6. dispatcher 呼叫但 work_order_id 不存在 → 404 透傳，非 RBAC 擋下
  7. customer_service 呼叫但缺 reason_text → 200 + audit log 記為「未提供理由」
  8. dispatcher 呼叫不寫 audit log（非繞過角色）
  9. customer_service 連續多次繞過 → 多筆 audit log
 10. brand_oem 呼叫 assignDispatch → 403

設計：mock work_order_service / dispatch_service 與 audit_log_service.log_event，
不依賴真實 DB；驗證 RBAC + audit hook 的呼叫契約。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    CUSTOMER_SERVICE_USER_ID,
    DISPATCHER_USER_ID,
    _make_token,
    DEFAULT_TENANT_ID,
)

pytestmark = pytest.mark.component


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fake_work_order(wo_id: str, technician_id: str) -> dict:
    """產 work_order_service 回傳的字典（對齊 WorkOrder schema）。"""
    return {
        "id": wo_id,
        "problem_card_id": str(uuid.uuid4()),
        "technician_id": technician_id,
        "status": "assigned",
        "district": "中正區",
        "address": "台北市中正區重慶南路一段122號",
        "brand": "Chatlock",
        "model": "AI-99",
        "urgency": "medium",
        "estimated_reward": "1500.00",
        "created_at": "2026-05-08T10:00:00+00:00",
        "updated_at": "2026-05-08T10:00:00+00:00",
    }


def _assign_body(technician_id: str, *, reason_text: str | None = "客戶要求特定技師") -> dict:
    return {
        "technician_id": technician_id,
        "reason_code": "customer_requested_specific_tech",
        "reason_text": reason_text,
    }


def _dispatch_body(
    work_order_id: str,
    technician_id: str,
    *,
    override_reason: str | None = "客戶指定",
) -> dict:
    return {
        "work_order_id": work_order_id,
        "technician_id": technician_id,
        "override_reason": override_reason,
    }


# ---------------------------------------------------------------------------
# Case 1 — dispatcher → assignWorkOrder 200（Q1=A 主路徑）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatcher_can_assign_work_order(client, dispatcher_headers):
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={**dispatcher_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_assign_body(tech_id),
        )

    assert res.status_code == 200, res.text
    assert res.json()["data"]["id"] == wo_id
    # dispatcher 不是 bypass 角色，audit hook 不應被呼叫
    mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Case 2 — customer_service → assignWorkOrder 200 + audit log（Q6=A）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_customer_service_bypass_writes_audit_log(
    client, customer_service_headers
):
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={
                **customer_service_headers,
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json=_assign_body(tech_id, reason_text="客戶投訴 SLA — 客服繞過"),
        )

    assert res.status_code == 200, res.text
    mock_audit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Case 3 — technician → 403（不允許角色）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_technician_cannot_assign_work_order(client, technician_headers):
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    with patch(
        "services.work_order_service.assign_order",
        new_callable=AsyncMock,
    ) as mock_assign:
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={**technician_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_assign_body(tech_id),
        )

    assert res.status_code == 403
    # RBAC 應在 service 之前擋下，不應呼叫到業務邏輯
    mock_assign.assert_not_called()


# ---------------------------------------------------------------------------
# Case 4 — dispatcher → assignDispatch 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatcher_can_assign_dispatch(client, dispatcher_headers):
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.dispatch_service.assign_dispatch",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            "/api/v1/dispatch/assign",
            headers={**dispatcher_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_dispatch_body(wo_id, tech_id),
        )

    assert res.status_code == 200, res.text
    assert res.json()["data"]["id"] == wo_id
    mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Case 5 — audit log payload 完整性（Q6=A 強制要求）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_customer_service_audit_log_payload_shape(
    client, customer_service_headers
):
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    reason = "客戶 LINE 訊息直接指名張師傅"
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={
                **customer_service_headers,
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json=_assign_body(tech_id, reason_text=reason),
        )

    assert res.status_code == 200, res.text
    mock_audit.assert_awaited_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["event_type"] == "dispatch_decision"
    assert kwargs["actor_id"] == CUSTOMER_SERVICE_USER_ID
    assert kwargs["actor_role"] == "customer_service"
    assert kwargs["action"] == "manual_dispatch_bypass"
    assert kwargs["target_type"] == "work_order"
    assert kwargs["target_id"] == wo_id
    payload = kwargs["payload"]
    assert payload["endpoint"] == "assignWorkOrder"
    assert payload["technician_id"] == tech_id
    assert payload["reason_code"] == "customer_requested_specific_tech"
    assert payload["reason_text"] == reason


# ---------------------------------------------------------------------------
# Case 6 — dispatcher 但工單不存在 → 404 透傳
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatcher_assign_nonexistent_work_order_returns_404(
    client, dispatcher_headers
):
    from core.errors import ApiError

    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            side_effect=ApiError("WORK_ORDER_NOT_FOUND", "Not found", 404),
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={**dispatcher_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_assign_body(tech_id),
        )

    assert res.status_code == 404
    mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Case 7 — customer_service 缺 reason_text → 仍可繞過，audit 記「未提供理由」
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_customer_service_bypass_without_reason_text(
    client, customer_service_headers
):
    """reason_text 為 optional；缺值時 audit log 仍寫入並記錄為「未提供理由」。"""
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    body = {
        "technician_id": tech_id,
        "reason_code": "customer_requested_specific_tech",
        # 不帶 reason_text
    }

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={
                **customer_service_headers,
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json=body,
        )

    assert res.status_code == 200, res.text
    mock_audit.assert_awaited_once()
    payload = mock_audit.call_args.kwargs["payload"]
    assert payload["reason_text"] == "未提供理由"


# ---------------------------------------------------------------------------
# Case 8 — admin（既有角色）→ 200，且不寫 bypass audit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_assign_does_not_write_bypass_audit(
    client, admin_headers
):
    """admin 不算「繞過」— 走自己的權限線，不該觸發 dispatch_bypass audit。"""
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        res = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_assign_body(tech_id),
        )

    assert res.status_code == 200, res.text
    mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Case 9 — customer_service 連續多次繞過 → 多筆 audit log
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repeated_bypass_writes_multiple_audit_entries(
    client, customer_service_headers
):
    """連續 3 次繞過必須產生 3 筆 audit。"""
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    fake_order = _fake_work_order(wo_id, tech_id)

    with (
        patch(
            "services.work_order_service.assign_order",
            new_callable=AsyncMock,
            return_value=fake_order,
        ),
        patch(
            "services.audit_log_service.log_event", new_callable=AsyncMock
        ) as mock_audit,
    ):
        for i in range(3):
            res = await client.post(
                f"/api/v1/work-orders/{wo_id}/assign",
                headers={
                    **customer_service_headers,
                    "Idempotency-Key": str(uuid.uuid4()),
                },
                json=_assign_body(tech_id, reason_text=f"繞過理由 #{i + 1}"),
            )
            assert res.status_code == 200, res.text

    assert mock_audit.await_count == 3


# ---------------------------------------------------------------------------
# Case 10 — brand_oem → assignDispatch 403（同 RBAC 擋）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_brand_oem_cannot_assign_dispatch(client):
    """brand_oem 不在 _DISPATCH_ALLOWED_ROLES 內 → 403。"""
    brand_user_id = "44444444-4444-4444-4444-444444444444"
    token = _make_token(user_id=brand_user_id, role="brand_oem")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }
    wo_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    with patch(
        "services.dispatch_service.assign_dispatch",
        new_callable=AsyncMock,
    ) as mock_assign:
        res = await client.post(
            "/api/v1/dispatch/assign",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            json=_dispatch_body(wo_id, tech_id),
        )

    assert res.status_code == 403
    mock_assign.assert_not_called()
