"""CR-0110 報價主檔 CRUD（20260702 會議裁決簡化版）。

單品牌 DB → code 唯一即可;軟刪 deleted_at;編輯後 is_mock=FALSE +
decision_status='已確認'(業主 2026-07-03 裁決)。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

TENANT = "00000000-0000-0000-0000-000000000001"


def _idem() -> dict:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _cleanup(table: str, col: str, code: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(f"DELETE FROM {table} WHERE {col} = %s", (code,))


@pytest.mark.component
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "segment,table,col,create_body,patch_body,name_field",
    [
        (
            "services", "service_catalog", "service_code",
            {"service_name": "測試開鎖服務", "unit": "次", "suggested_customer_price": 1500},
            {"suggested_customer_price": 1800},
            "service_name",
        ),
        (
            "materials", "material_catalog", "material_code",
            {"material_name": "測試鎖芯", "unit": "顆", "suggested_price": 900},
            {"suggested_price": 950},
            "material_name",
        ),
        (
            "surcharges", "surcharge_rule", "rule_code",
            {"rule_name": "測試夜間加價", "rule_type": "night", "amount": 500},
            {"amount": 600},
            "rule_name",
        ),
    ],
)
async def test_catalog_crud_lifecycle(
    client, admin_headers, segment, table, col, create_body, patch_body, name_field
):
    code = f"E2E-{segment[:3].upper()}-{uuid.uuid4().hex[:6]}"
    try:
        # Create → 201,寫入即租戶確認值
        r = await client.post(
            f"/tenants/{TENANT}/quote-catalog/{segment}",
            json={"code": code, **create_body},
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 201, r.text

        cur = await db_module._conn.execute(
            f"SELECT is_mock, decision_status, tenant_id FROM {table} WHERE {col} = %s",
            (code,),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row[0] is False           # is_mock 翻 FALSE(§8-6)
        assert row[1] == "已確認"
        assert str(row[2]) == TENANT

        # 重複 code → 409
        r = await client.post(
            f"/tenants/{TENANT}/quote-catalog/{segment}",
            json={"code": code, **create_body},
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "CODE_TAKEN"

        # GET 出現在 catalog
        r = await client.get(f"/tenants/{TENANT}/quote-catalog", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()[segment]
        assert any(i.get(col) == code for i in items)

        # PATCH → 200
        r = await client.patch(
            f"/tenants/{TENANT}/quote-catalog/{segment}/{code}",
            json=patch_body,
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text

        # DELETE(軟刪)→ 200;列表消失、DB 列還在
        r = await client.delete(
            f"/tenants/{TENANT}/quote-catalog/{segment}/{code}",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        r = await client.get(f"/tenants/{TENANT}/quote-catalog", headers=admin_headers)
        assert not any(i.get(col) == code for i in r.json()[segment])
        cur = await db_module._conn.execute(
            f"SELECT deleted_at FROM {table} WHERE {col} = %s", (code,)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is not None  # 軟刪:列在、deleted_at 落

        # 刪後再刪 → 404
        r = await client.delete(
            f"/tenants/{TENANT}/quote-catalog/{segment}/{code}",
            headers=admin_headers,
        )
        assert r.status_code == 404

        # 軟刪後 code 可重建(唯一性只看未刪列)
        r = await client.post(
            f"/tenants/{TENANT}/quote-catalog/{segment}",
            json={"code": code, **create_body},
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 201, r.text
    finally:
        await _cleanup(table, col, code)


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_missing_name_422(client, admin_headers):
    r = await client.post(
        f"/tenants/{TENANT}/quote-catalog/services",
        json={"code": f"E2E-VAL-{uuid.uuid4().hex[:6]}", "unit": "次"},
        headers={**admin_headers, **_idem()},
    )
    assert r.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_negative_price_422(client, admin_headers):
    r = await client.post(
        f"/tenants/{TENANT}/quote-catalog/services",
        json={
            "code": f"E2E-NEG-{uuid.uuid4().hex[:6]}",
            "service_name": "負數測試",
            "suggested_customer_price": -100,
        },
        headers={**admin_headers, **_idem()},
    )
    assert r.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_unknown_segment_404(client, admin_headers):
    r = await client.post(
        f"/tenants/{TENANT}/quote-catalog/nope",
        json={"code": "X", "service_name": "x"},
        headers={**admin_headers, **_idem()},
    )
    assert r.status_code == 404


@pytest.mark.component
@pytest.mark.asyncio
async def test_technician_role_403(client, technician_headers):
    r = await client.post(
        f"/tenants/{TENANT}/quote-catalog/services",
        json={"code": "E2E-RBAC-X", "service_name": "x"},
        headers={**technician_headers, **_idem()},
    )
    assert r.status_code == 403
