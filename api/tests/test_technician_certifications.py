"""CR-0104 技能認證矩陣（technician_certification）端點測試。

CR-0114 收斂：認證屬師傅身分域資質，歸平台方職權 —— 品牌端寫端點
（POST/PATCH/DELETE）已廢止,只留 GET 唯讀。涵蓋：
  C-1  GET 列表 → 含直插測資 + status computed（過期/即將到期/有效/無到期）
  C-2  品牌端 POST/PATCH/DELETE → 405（契約回歸守衛）
  C-3  cross-tenant GET → 403

測資由直插 DB 建立（原品牌端 POST 建立路徑已廢止）。
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


async def _create_technician() -> str:
    """直插一列最小 technicians 測資。"""
    import core.db as db_module

    assert await db_module._ensure_conn()
    tech_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, name, phone, capabilities, service_regions, status) "
        "VALUES (%s::uuid, %s::uuid, %s, '0900000000', '[]'::jsonb, '[\"taipei\"]'::jsonb, 'active')",
        (tech_id, DEFAULT_TENANT_ID, f"cert-test-{tech_id[:8]}"),
    )
    return tech_id


async def _insert_cert(tech_id: str, cert_name: str, expires_at: str | None) -> str:
    import core.db as db_module

    cert_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO technician_certification "
        "  (id, tenant_id, technician_id, cert_name, brand, obtained_at, expires_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'Yale', '2025-01-01', %s)",
        (cert_id, DEFAULT_TENANT_ID, tech_id, cert_name, expires_at),
    )
    return cert_id


async def _cleanup_technician(tech_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM technician_certification WHERE technician_id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))


def _cert_path(tech_id: str, cert_id: str | None = None) -> str:
    base = f"/tenants/{DEFAULT_TENANT_ID}/technicians/{tech_id}/certifications"
    return f"{base}/{cert_id}" if cert_id else base


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_list_and_status_computation(client, admin_headers):
    """C-1：GET 列表含直插測資,status 由 expires_at vs 今日 computed。"""
    tech_id = await _create_technician()
    today = date.today()
    cases = [
        ((today - timedelta(days=10)).isoformat(), "expired"),        # 過期
        ((today + timedelta(days=15)).isoformat(), "expiring_soon"),  # 30 天內
        ((today + timedelta(days=365)).isoformat(), "valid"),         # 遠期
        (None, "valid"),                                              # 無到期
    ]
    try:
        expected_by_name: dict[str, str] = {}
        for expires_at, expected in cases:
            name = f"認證-{expected}-{str(uuid.uuid4())[:6]}"
            await _insert_cert(tech_id, name, expires_at)
            expected_by_name[name] = expected

        lst = await client.get(_cert_path(tech_id), headers=admin_headers)
        assert lst.status_code == 200, lst.text
        items = {c["cert_name"]: c for c in lst.json()["data"]}
        for name, expected in expected_by_name.items():
            assert name in items, f"列表缺 {name}"
            assert items[name]["status"] == expected, (name, expected)
            assert items[name]["brand"] == "Yale"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_brand_certification_write_endpoints_removed(client, admin_headers):
    """C-2：品牌端認證寫端點已廢止（CR-0114 裁決 1「品牌端唯讀」）→ 405。"""
    tech_id = await _create_technician()
    try:
        post = await client.post(
            _cert_path(tech_id),
            json={"cert_name": "不該建得成"},
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert post.status_code == 405, post.text

        # PATCH/DELETE 的 /{certId} 路徑整條移除（該路徑無任何殘留方法）→ 404
        cert_id = await _insert_cert(tech_id, "既有認證", None)
        patch = await client.patch(
            _cert_path(tech_id, cert_id),
            json={"cert_name": "不該改得動"},
            headers=admin_headers,
        )
        assert patch.status_code == 404, patch.text

        dele = await client.delete(_cert_path(tech_id, cert_id), headers=admin_headers)
        assert dele.status_code == 404, dele.text
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_certification_cross_tenant_403(client, admin_headers):
    """C-3：JWT tenant 與 path tenantId 不符 → GET 403。"""
    tech_id = await _create_technician()
    try:
        res = await client.get(
            f"/tenants/{OTHER_TENANT_ID}/technicians/{tech_id}/certifications",
            headers=admin_headers,
        )
        assert res.status_code == 403, res.text
        assert res.json().get("error_code") == "CROSS_TENANT_READ"
    finally:
        await _cleanup_technician(tech_id)
