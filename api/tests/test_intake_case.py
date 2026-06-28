"""CR-0108 M01 進線 Case 入口端點測試。

  IC-1 客服代建 Case → 201 + 可讀號 C-NNNNNN + first_response_due_at（SLA 啟動）
  IC-2 列表 + status / source_channel 篩選
  IC-3 詳情 + sla_overdue 衍生旗標
  IC-4 更新 status=in_progress → 記 first_responded_at
  IC-5 非法 source_channel（partner 渠道 Phase II）→ 422
  IC-6 cross-tenant → 403
  IC-7 不存在 case → 404
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


def _path(case_id: str | None = None) -> str:
    base = f"/tenants/{DEFAULT_TENANT_ID}/cases"
    return f"{base}/{case_id}" if case_id else base


async def _cleanup(case_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM saas.intake_case WHERE id = %s::uuid", (case_id,)
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_lists_and_detail(client, admin_headers):
    """IC-1/IC-2/IC-3：建案 → 可讀號 + SLA → 列表/篩選 → 詳情。"""
    res = await client.post(
        _path(),
        json={"source_channel": "phone", "summary": "電話報修 門鎖卡住", "customer_name": "王先生",
              "customer_phone": "0912345678"},
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201, res.text
    case = res.json()["data"]
    cid = case["id"]
    try:
        assert case["case_number"].startswith("C-") and len(case["case_number"]) == 8
        assert case["source_channel"] == "phone"
        assert case["status"] == "open"
        assert case["first_response_due_at"] is not None  # SLA 已啟動
        assert case["first_responded_at"] is None

        # 列表含 + source_channel 篩選
        lst = await client.get(_path() + "?source_channel=phone", headers=admin_headers)
        assert lst.status_code == 200
        assert any(c["id"] == cid for c in lst.json()["data"])

        # 詳情 + sla_overdue（剛建未逾時）
        det = await client.get(_path(cid), headers=admin_headers)
        assert det.status_code == 200
        assert det.json()["data"]["sla_overdue"] is False
    finally:
        await _cleanup(cid)


@pytest.mark.asyncio
@pytest.mark.component
async def test_update_status_records_first_response(client, admin_headers):
    """IC-4：status=in_progress → 記 first_responded_at。"""
    res = await client.post(
        _path(),
        json={"source_channel": "web", "summary": "官網表單進線"},
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    cid = res.json()["data"]["id"]
    try:
        upd = await client.patch(
            _path(cid), json={"status": "in_progress"}, headers=admin_headers
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["data"]["status"] == "in_progress"
        assert upd.json()["data"]["first_responded_at"] is not None
    finally:
        await _cleanup(cid)


@pytest.mark.asyncio
@pytest.mark.component
async def test_invalid_source_channel_422(client, admin_headers):
    """IC-5：partner 渠道（Phase II）非法 → 422。"""
    res = await client.post(
        _path(),
        json={"source_channel": "brand", "summary": "x"},
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
@pytest.mark.component
async def test_cross_tenant_403(client, admin_headers):
    """IC-6：cross-tenant 建案 → 403。"""
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/cases",
        json={"source_channel": "line"},
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_not_found_404(client, admin_headers):
    """IC-7：不存在 case → 404。"""
    res = await client.get(_path(str(uuid.uuid4())), headers=admin_headers)
    assert res.status_code == 404, res.text
