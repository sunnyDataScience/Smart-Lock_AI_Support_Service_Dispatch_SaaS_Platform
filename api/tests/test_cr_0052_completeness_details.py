"""CR-0052 完整度 422 結構化缺漏欄位測試（前端可逐欄高亮）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import problem_card_service as pcs

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _insert_pc(pc_id, *, model="YDM-4109"):
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, brand, model, symptoms, urgency, status) "
        "VALUES (%s::uuid, 'Yale', %s, '[\"電池\"]'::jsonb, 'normal', 'incomplete')",
        (pc_id, model))


@pytest.mark.asyncio
async def test_incomplete_422_has_structured_details():
    assert await db_module._ensure_conn()
    pc = str(uuid.uuid4())
    await _insert_pc(pc, model="")  # 缺 model + 缺 address → < 0.8
    try:
        with pytest.raises(ApiError) as ei:
            await pcs.assert_completeness(tenant_id=TID, pc_id=pc, customer_address=None)
        err = ei.value
        assert err.error_code == "INCOMPLETE_PROBLEM_CARD"
        # 結構化 details：每個缺漏欄位一筆 {field, issue}
        assert isinstance(err.details, list) and len(err.details) >= 1
        fields = {d["field"] for d in err.details}
        assert "model" in fields and "customer_address" in fields
        assert all(d["issue"] == "missing" for d in err.details)
    finally:
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pc,))
