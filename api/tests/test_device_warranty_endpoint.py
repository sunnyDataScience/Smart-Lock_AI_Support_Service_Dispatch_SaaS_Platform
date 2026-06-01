"""Device Warranty 端點元件測試（需 live DB — gated by @pytest.mark.component）。

對齊 spec: GET / PATCH /tenants/{tenantId}/devices/{deviceId}/warranty
（ADR-0044 v2 / FR-0015 / BR-WARRANTY-006）。

驗證：
  - GET 回 warranty_start_mode / start / end / period_months / coverage_class
  - PATCH manual_override 主管核可 → 202 pending
  - PATCH B2B override 61 → 422（上限 60）
  - PATCH 非 manual_override → 422
  - SoD initiator == approver → 403

⚠ 本切片 device_warranty 獨立表尚未建（spec saas.device_warranty 留待 P3）；
GET 以 5-mode 純函式 best-effort 推算，不查 device 表，因此不需建 device fixture。
若 DB / auth fixture 跑不起來，整檔依 @pytest.mark.component 被預設略過。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _path(device_id: str) -> str:
    return f"/tenants/{DEFAULT_TENANT_ID}/devices/{device_id}/warranty"


def _sod_headers(base_headers: dict, *, initiator="csm-1", approver="sup-1", executor=None) -> dict:
    h = dict(base_headers)
    h["Idempotency-Key"] = str(uuid.uuid4())
    h["X-Initiator"] = initiator
    h["X-Approver"] = approver
    if executor:
        h["X-Executor"] = executor
    return h


@pytest.mark.asyncio
async def test_get_device_warranty_returns_mode_and_dates(client, admin_headers):
    device_id = str(uuid.uuid4())
    res = await client.get(_path(device_id), headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["device_id"] == device_id
    assert data["warranty_start_mode"] in (
        "purchase_date", "install_date", "handover_date",
        "brand_warranty_date", "contract_date", "manual_override",
    )
    assert data["warranty_start_date"]
    assert data["warranty_end_date"]
    assert data["warranty_period_months"] == 24
    assert data["coverage_class"] in ("full", "parts_only", "labor_only", "expired")


@pytest.mark.asyncio
async def test_patch_manual_override_supervisor_returns_202(client, admin_headers):
    # admin 在 _SUPERVISOR_ROLES 內 → 可核可
    device_id = str(uuid.uuid4())
    res = await client.patch(
        _path(device_id),
        headers=_sod_headers(admin_headers),
        json={"new_mode": "manual_override", "new_start_date": "2026-01-01", "reason": "缺購買日，人工指定"},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "pending_supervisor_approval"
    assert body["device_id"] == device_id


@pytest.mark.asyncio
async def test_patch_override_exceeds_cap_422(client, admin_headers):
    device_id = str(uuid.uuid4())
    res = await client.patch(
        _path(device_id),
        headers=_sod_headers(admin_headers),
        json={"new_mode": "manual_override", "period_months_override": 61, "reason": "B2B 長約"},
    )
    # pydantic le=60 會先擋（422），或 service 端 validate_b2b_override 擋（422）
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_non_manual_override_mode_422(client, admin_headers):
    device_id = str(uuid.uuid4())
    res = await client.patch(
        _path(device_id),
        headers=_sod_headers(admin_headers),
        json={"new_mode": "purchase_date", "reason": "想改 mode"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_sod_violation_403(client, admin_headers):
    device_id = str(uuid.uuid4())
    res = await client.patch(
        _path(device_id),
        headers=_sod_headers(admin_headers, initiator="same", approver="same"),
        json={"new_mode": "manual_override", "reason": "test"},
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "SOD_VIOLATION"
