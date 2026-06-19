"""CR-0057 M03 三級必填分類落地測試（required/pre_dispatch/optional）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import problem_card_service as pcs

TID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.unit
def test_field_tiers_classification():
    t = pcs.required_field_tiers()
    assert "brand" in t["required"] and "model" in t["required"]
    assert "customer_address" in t["pre_dispatch"]
    assert pcs._field_tier("brand") == "required"
    assert pcs._field_tier("customer_address") == "pre_dispatch"
    assert pcs._field_tier("serial_number") == "optional"
    assert pcs._field_tier("unknown_x") == "optional"


@pytest.mark.component
@pytest.mark.asyncio
async def test_completeness_422_details_have_tier():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, brand, model, symptoms, urgency, status) "
        "VALUES (%s::uuid, 'Yale', '', '[\"電池\"]'::jsonb, 'normal', 'incomplete')", (pc,))
    try:
        with pytest.raises(ApiError) as ei:
            await pcs.assert_completeness(tenant_id=TID, pc_id=pc, customer_address=None)
        details = ei.value.details
        tiers = {d["field"]: d["tier"] for d in details}
        assert tiers.get("model") == "required"
        assert tiers.get("customer_address") == "pre_dispatch"
    finally:
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pc,))
