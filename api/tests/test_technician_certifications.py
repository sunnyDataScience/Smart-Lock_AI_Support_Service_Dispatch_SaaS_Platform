"""CR-0104 技能認證矩陣（technician_certification）端點測試。

涵蓋：
  C-1  POST 新增認證 → 201 + status computed
  C-2  GET 列表 → 含新增筆
  C-3  PATCH 編輯 → 欄位更新
  C-4  DELETE 刪除 → 列表清空
  C-5  狀態計算：過期 / 即將到期 / 有效 / 無到期
  C-6  cross-tenant POST → 403
  C-7  對不存在技師新增 → 404

每個 component 測試自建技師 + 清理（避免污染 dev DB；create_technician 會一併建 user）。
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


async def _create_technician(client, admin_headers) -> str:
    idem = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"display_name": f"cert-test-{idem[:8]}", "coverage_areas": ["taipei"]},
        headers={**admin_headers, "Idempotency-Key": idem},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _cleanup_technician(tech_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id = %s::uuid", (tech_id,))
    row = await cur.fetchone()
    await db_module._conn.execute(
        "DELETE FROM technician_certification WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    if row and row[0]:
        await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (row[0],))


def _cert_path(tech_id: str, cert_id: str | None = None) -> str:
    base = f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}/certifications"
    return f"{base}/{cert_id}" if cert_id else base


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_crud_lifecycle(client, admin_headers):
    """C-1~C-4：建立 → 列表 → 編輯 → 刪除 全流程。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        # C-1 建立
        res = await client.post(
            _cert_path(tech_id),
            json={"cert_name": "電子鎖安裝認證", "brand": "Yale", "obtained_at": "2025-01-01"},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201, res.text
        cert = res.json()["data"]
        cert_id = cert["id"]
        assert cert["cert_name"] == "電子鎖安裝認證"
        assert cert["brand"] == "Yale"
        assert cert["status"] == "valid"  # 無到期日 → valid

        # C-2 列表
        lst = await client.get(_cert_path(tech_id), headers=admin_headers)
        assert lst.status_code == 200, lst.text
        items = lst.json()["data"]
        assert any(c["id"] == cert_id for c in items)

        # C-3 編輯
        patch = await client.patch(
            _cert_path(tech_id, cert_id),
            json={"cert_name": "電子鎖安裝認證（進階）", "brand": "Kaadas"},
            headers=admin_headers,
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["data"]["cert_name"] == "電子鎖安裝認證（進階）"
        assert patch.json()["data"]["brand"] == "Kaadas"

        # C-4 刪除
        dele = await client.delete(_cert_path(tech_id, cert_id), headers=admin_headers)
        assert dele.status_code == 200, dele.text
        lst2 = await client.get(_cert_path(tech_id), headers=admin_headers)
        assert all(c["id"] != cert_id for c in lst2.json()["data"])
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_status_computation(client, admin_headers):
    """C-5：狀態由 expires_at vs 今日 computed。"""
    tech_id = await _create_technician(client, admin_headers)
    today = date.today()
    cases = [
        ((today - timedelta(days=10)).isoformat(), "expired"),       # 過期
        ((today + timedelta(days=15)).isoformat(), "expiring_soon"),  # 30 天內
        ((today + timedelta(days=365)).isoformat(), "valid"),         # 遠期
        (None, "valid"),                                              # 無到期
    ]
    try:
        for expires_at, expected in cases:
            res = await client.post(
                _cert_path(tech_id),
                json={"cert_name": f"認證-{expected}", "expires_at": expires_at},
                headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert res.status_code == 201, res.text
            assert res.json()["data"]["status"] == expected, (expires_at, expected)
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_cross_tenant_403(client, admin_headers):
    """C-6：JWT tenant 與 path tenantId 不符 → 403。"""
    tech_id = await _create_technician(client, admin_headers)
    try:
        res = await client.post(
            f"/tenants/{OTHER_TENANT_ID}/technicians/{tech_id}/certifications",
            json={"cert_name": "x"},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 403, res.text
        assert res.json().get("error_code") == "CROSS_TENANT_WRITE"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_missing_technician_404(client, admin_headers):
    """C-7：對不存在技師新增 → 404。"""
    ghost = str(uuid.uuid4())
    res = await client.post(
        _cert_path(ghost),
        json={"cert_name": "x"},
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 404, res.text
