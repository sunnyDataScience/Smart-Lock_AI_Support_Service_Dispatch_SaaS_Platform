"""CR-0100 工單詳情頁 B 類後端欄位測試。

涵蓋：
  - SLA deadline computed（_compute_sla_deadline）：三級時數、缺時間回 None。
  - 功能測試 Pydantic 驗證：result ∈ pass/fail/na；非法值 422；completion request 接受。
  - WorkOrder model 新欄位存在（completion_summary / function_tests / sla_deadline）。

_compute_sla_deadline 讀 M18 config sla_policy（DB）→ component（migration 079 已套用）。
Pydantic / model 測試 DB-free。
"""

from __future__ import annotations

import pytest


# ── SLA deadline computed（component：讀 sla_policy config）────────────────────
@pytest.mark.component
@pytest.mark.asyncio
async def test_sla_deadline_high_8h():
    """urgency=high → deadline = created_at + 8h（sla_policy default）。"""
    from services.work_order_service import _compute_sla_deadline

    out = await _compute_sla_deadline("2026-06-25T00:00:00+00:00", "high")
    assert out is not None
    assert out.startswith("2026-06-25T08:00")


@pytest.mark.component
@pytest.mark.asyncio
async def test_sla_deadline_low_48h():
    from services.work_order_service import _compute_sla_deadline

    out = await _compute_sla_deadline("2026-06-25T00:00:00+00:00", "low")
    assert out is not None
    assert out.startswith("2026-06-27T00:00")  # +48h = 隔兩天


@pytest.mark.asyncio
async def test_sla_deadline_none_when_no_created():
    from services.work_order_service import _compute_sla_deadline

    assert await _compute_sla_deadline(None, "high") is None
    assert await _compute_sla_deadline("2026-06-25T00:00:00+00:00", None) is None


# ── 功能測試 Pydantic 驗證（DB-free）─────────────────────────────────────────
def test_function_test_result_accepts_valid():
    from routers.work_orders_v2 import _FunctionTestResult

    for r in ("pass", "fail", "na"):
        m = _FunctionTestResult(key="fingerprint", result=r)
        assert m.result == r


def test_function_test_result_rejects_invalid():
    import pydantic

    from routers.work_orders_v2 import _FunctionTestResult

    with pytest.raises(pydantic.ValidationError):
        _FunctionTestResult(key="x", result="maybe")


def test_completion_request_accepts_function_tests():
    from routers.work_orders_v2 import _CompletionSubmitRequest

    req = _CompletionSubmitRequest(
        signature_evidence_id="sig",
        photo_evidence_ids=["p1"],
        function_tests=[{"key": "battery", "result": "fail"}],
    )
    assert req.function_tests is not None
    assert req.function_tests[0].key == "battery"
    assert req.function_tests[0].result == "fail"


def test_completion_request_function_tests_optional():
    from routers.work_orders_v2 import _CompletionSubmitRequest

    req = _CompletionSubmitRequest(
        signature_evidence_id="sig", photo_evidence_ids=["p1"]
    )
    assert req.function_tests is None


# ── WorkOrder model 新欄位（DB-free）─────────────────────────────────────────
def test_workorder_model_has_b_fields():
    from models.generated import WorkOrder

    fields = WorkOrder.model_fields
    assert "completion_summary" in fields
    assert "function_tests" in fields
    assert "sla_deadline" in fields
