"""CR-0026 公單標準化欄位測試。

兩層：
- 純函式（無 DB）：_wo_row_to_dict 把 migration 036 新欄位（index 15+）正確映射
- component（真 DB）：_assert_dispatch_ready 派工前必填 gate（BR-M05-03）
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from services import work_order_service as svc


# ---------------------------------------------------------------------------
# 純函式：serializer 映射（對齊 _WO_SELECT 28 欄順序）
# ---------------------------------------------------------------------------

def _full_row() -> tuple:
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    pid = uuid.uuid4()
    return (
        uuid.uuid4(),            # 0 id
        uuid.uuid4(),            # 1 problem_card_id
        None,                    # 2 technician_id
        "assigned",              # 3 status
        "high",                  # 4 priority
        "新北市板橋區文化路1號",   # 5 customer_address
        "Yale",                  # 6 brand
        "YDM-4109",              # 7 model
        None,                    # 8 estimated_price
        None,                    # 9 scheduled_at
        None,                    # 10 started_at
        None,                    # 11 completed_at
        now,                     # 12 created_at
        now,                     # 13 updated_at
        "PB-000123",             # 14 document_number
        "repair",                # 15 service_category
        "電池故障",               # 16 problem_type
        "SN-XYZ-001",            # 17 serial_number
        "木門",                   # 18 door_type
        "45mm",                  # 19 door_thickness
        True,                    # 20 is_interior_door
        "out_warranty",          # 21 warranty_status
        date(2024, 1, 1),        # 22 purchase_date
        "INV-2024-001",          # 23 invoice_no
        "pending_photos",        # 24 completion_status
        "客戶改期取消",            # 25 status_reason
        pid,                     # 26 parent_work_order_id
        1280.5,                  # 27 customer_final_amount
    )


def test_wo_row_to_dict_maps_new_fields():
    out = svc._wo_row_to_dict(_full_row())
    assert out["service_category"] == "repair"
    assert out["problem_type"] == "電池故障"
    assert out["serial_number"] == "SN-XYZ-001"
    assert out["door_type"] == "木門"
    assert out["door_thickness"] == "45mm"
    assert out["is_interior_door"] is True
    assert out["warranty_status"] == "out_warranty"
    assert out["purchase_date"] == "2024-01-01"
    assert out["invoice_no"] == "INV-2024-001"
    assert out["completion_status"] == "pending_photos"
    assert out["status_reason"] == "客戶改期取消"
    assert "parent_work_order_id" in out
    assert out["customer_final_amount"] == "1280.50"  # decimal 字串化


def test_wo_row_to_dict_backward_compatible_short_row():
    """舊 15 欄 row（無 CR-0026 欄位）仍可序列化、不報錯、不含新 key。"""
    short = _full_row()[:15]
    out = svc._wo_row_to_dict(short)
    assert out["brand"] == "Yale"
    assert "service_category" not in out
    assert "customer_final_amount" not in out


def test_wo_row_to_dict_none_new_fields_omitted():
    """新欄位為 None 時不輸出（保 response 精簡）。"""
    row = list(_full_row())
    for i in range(15, 28):
        row[i] = None
    out = svc._wo_row_to_dict(tuple(row))
    for k in ("service_category", "status_reason", "customer_final_amount", "is_interior_door"):
        assert k not in out


# ---------------------------------------------------------------------------
# component（真 DB）：派工前必填 gate
# ---------------------------------------------------------------------------

pytestmark_component = pytest.mark.component


@pytest.mark.component
@pytest.mark.asyncio
async def test_assert_dispatch_ready_gate(client):
    """缺問題類型 → 422；齊全 → 通過。直接 seed 最小 work_orders row（不走 PC 鏈）。"""
    import core.db as db_module
    from core.errors import ApiError

    assert await db_module._ensure_conn()

    wo_missing = str(uuid.uuid4())
    wo_ready = str(uuid.uuid4())
    # 缺 problem_type
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, brand, model) "
        "VALUES (%s::uuid, 'created', %s, %s, %s)",
        (wo_missing, "新北市板橋區文化路1號", "Yale", "YDM-4109"),
    )
    # 齊全
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, brand, model, problem_type) "
        "VALUES (%s::uuid, 'created', %s, %s, %s, %s)",
        (wo_ready, "新北市板橋區文化路1號", "Yale", "YDM-4109", "電池故障"),
    )
    try:
        with pytest.raises(ApiError) as ei:
            await svc._assert_dispatch_ready(wo_missing)
        assert ei.value.status_code == 422
        # 齊全不應 raise
        await svc._assert_dispatch_ready(wo_ready)
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE id IN (%s::uuid, %s::uuid)",
            (wo_missing, wo_ready),
        )
