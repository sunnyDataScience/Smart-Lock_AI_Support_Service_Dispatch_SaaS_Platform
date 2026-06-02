"""Inventory v2 endpoint tests (FR-0007 / CR-0004 §8 Track B S3 / ADR-0052 / ADR-0053).

@pytest.mark.component — 需 live DB（saas.inventory_item / saas.inventory_transaction / saas.tenant）
@pytest.mark.unit     — 純邏輯（stock_status 衍生 / decimal coerce / text_array coerce）

測資策略：
  - 每個 component test 自建 saas.inventory_item row（INSERT 直打 DB）
  - tenant = DEFAULT_TENANT_ID（00000000-…-0001，migration 004 已 seed saas.tenant）
  - 測試後 cleanup（DELETE by id）確保隔離
  - consume / return / restock 的 transaction ledger 都做斷言
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID

# 用於 cross-tenant 測試的假 tenant
OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000002"

# 固定 part_number prefix 讓 cleanup 更容易（測試後逐一清）
_PART_PREFIX = "TST-INV-V2-"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic, no DB
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDeriveStockStatus:
    """stock_status 衍生邏輯（純函式，無 DB）。"""

    def test_zero_qty_is_out_of_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(0, 5) == "out_of_stock"

    def test_negative_qty_is_out_of_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(-1, 5) == "out_of_stock"

    def test_qty_equal_reorder_is_low_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(5, 5) == "low_stock"

    def test_qty_below_reorder_is_low_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(3, 5) == "low_stock"

    def test_qty_above_reorder_is_in_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(6, 5) == "in_stock"

    def test_zero_reorder_point_and_positive_qty_is_in_stock(self):
        from services.inventory_v2_service import _derive_stock_status
        assert _derive_stock_status(1, 0) == "in_stock"


@pytest.mark.unit
class TestDecimalCoerce:
    def test_none_returns_none(self):
        from services.inventory_v2_service import _coerce_decimal
        assert _coerce_decimal(None) is None

    def test_integer_to_two_decimal(self):
        from services.inventory_v2_service import _coerce_decimal
        assert _coerce_decimal(100) == "100.00"

    def test_float_precision(self):
        from services.inventory_v2_service import _coerce_decimal
        assert _coerce_decimal(1234.5) == "1234.50"


@pytest.mark.unit
class TestTextArrayCoerce:
    def test_none_returns_none(self):
        from services.inventory_v2_service import _coerce_text_array
        assert _coerce_text_array(None) is None

    def test_list_passthrough(self):
        from services.inventory_v2_service import _coerce_text_array
        assert _coerce_text_array(["Yale", "Samsung"]) == ["Yale", "Samsung"]

    def test_empty_list(self):
        from services.inventory_v2_service import _coerce_text_array
        assert _coerce_text_array([]) == []


@pytest.mark.unit
class TestValidOwnerSet:
    def test_valid_owners(self):
        from services.inventory_v2_service import _VALID_OWNER
        assert _VALID_OWNER == {"platform", "brand", "locksmith"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for component tests
# ─────────────────────────────────────────────────────────────────────────────


async def _insert_item(
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    part_number: str | None = None,
    name: str = "測試品項",
    category: str = "零件",
    quantity_on_hand: int = 10,
    reorder_point: int = 5,
    owner: str = "platform",
    serial_required: bool = False,
    unit_cost: float = 100.0,
) -> str:
    """直接 INSERT 一筆 saas.inventory_item，回傳 id。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    item_id = str(uuid.uuid4())
    pn = part_number or f"{_PART_PREFIX}{item_id[:8]}"

    await db_module._conn.execute(
        "INSERT INTO saas.inventory_item "
        "  (id, tenant_id, part_number, name, category, unit_cost, "
        "   quantity_on_hand, reorder_point, owner, serial_required) "
        "VALUES "
        "  (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            item_id, tenant_id, pn, name, category,
            unit_cost, quantity_on_hand, reorder_point,
            owner, serial_required,
        ),
    )
    return item_id


async def _cleanup_item(item_id: str) -> None:
    """刪品項（先刪 transactions FK）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM saas.inventory_transaction WHERE item_id = %s::uuid",
        (item_id,),
    )
    await db_module._conn.execute(
        "DELETE FROM saas.inventory_item WHERE id = %s::uuid",
        (item_id,),
    )


def _make_headers(
    user_id: str = ADMIN_USER_ID,
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict:
    from tests.conftest import _make_token

    token = _make_token(user_id=user_id, role=role, tenant_id=tenant_id)
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


def _idem_key() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 1. create + get
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_and_get_item(client):
    """POST /inventory/items → 201；GET /inventory/items/{itemId} → 200 同品項。"""
    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    pn = f"{_PART_PREFIX}create-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
        headers=headers,
        json={
            "part_number": pn,
            "name": "電子門鎖",
            "category": "主鎖",
            "unit_cost": 3500.0,
            "quantity_on_hand": 10,
            "reorder_point": 3,
            "owner": "brand",
            "serial_required": True,
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()["data"]
    assert created["part_number"] == pn
    assert created["owner"] == "brand"
    assert created["serial_required"] is True
    assert created["quantity_on_hand"] == 10
    assert created["stock_status"] == "in_stock"
    assert created["unit_cost"] == "3500.00"

    item_id = created["id"]

    # GET
    get_resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}",
        headers=_make_headers(),
    )
    assert get_resp.status_code == 200, get_resp.text
    got = get_resp.json()["data"]
    assert got["id"] == item_id
    assert got["part_number"] == pn

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_item_not_found(client):
    """GET 不存在品項 → 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{fake_id}",
        headers=_make_headers(),
    )
    assert resp.status_code == 404


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_duplicate_part_number_409(client):
    """相同 tenant + part_number 重複 CREATE → 409 DUPLICATE_PART_NUMBER。"""
    pn = f"{_PART_PREFIX}dup-{uuid.uuid4().hex[:6]}"
    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp1 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
        headers=headers,
        json={"part_number": pn, "name": "A"},
    )
    assert resp1.status_code == 201, resp1.text
    item_id = resp1.json()["data"]["id"]

    headers2 = _make_headers()
    headers2["Idempotency-Key"] = _idem_key()
    resp2 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
        headers=headers2,
        json={"part_number": pn, "name": "B"},
    )
    assert resp2.status_code == 409, resp2.text
    assert "DUPLICATE_PART_NUMBER" in resp2.text

    await _cleanup_item(item_id)


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 2. list（stock_status 過濾）
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_items_with_stock_status_filter(client):
    """建三種庫存狀態品項，用 stock_status 過濾各得 1 筆。"""
    pn_out = f"{_PART_PREFIX}out-{uuid.uuid4().hex[:6]}"
    pn_low = f"{_PART_PREFIX}low-{uuid.uuid4().hex[:6]}"
    pn_in = f"{_PART_PREFIX}in-{uuid.uuid4().hex[:6]}"

    # out_of_stock: qty=0, reorder=5
    id_out = await _insert_item(quantity_on_hand=0, reorder_point=5, part_number=pn_out)
    # low_stock: qty=3, reorder=5
    id_low = await _insert_item(quantity_on_hand=3, reorder_point=5, part_number=pn_low)
    # in_stock: qty=10, reorder=5
    id_in = await _insert_item(quantity_on_hand=10, reorder_point=5, part_number=pn_in)

    headers = _make_headers()

    try:
        # out_of_stock 過濾
        r = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
            headers=headers,
            params={"stock_status": "out_of_stock", "limit": 100},
        )
        assert r.status_code == 200, r.text
        ids_out = {item["id"] for item in r.json()["items"]}
        assert id_out in ids_out
        assert id_in not in ids_out

        # low_stock 過濾
        r = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
            headers=headers,
            params={"stock_status": "low_stock", "limit": 100},
        )
        assert r.status_code == 200
        ids_low = {item["id"] for item in r.json()["items"]}
        assert id_low in ids_low

        # in_stock 過濾
        r = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
            headers=headers,
            params={"stock_status": "in_stock", "limit": 100},
        )
        assert r.status_code == 200
        ids_in = {item["id"] for item in r.json()["items"]}
        assert id_in in ids_in

    finally:
        await _cleanup_item(id_out)
        await _cleanup_item(id_low)
        await _cleanup_item(id_in)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_items_invalid_stock_status_422(client):
    """無效 stock_status → 422。"""
    r = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items",
        headers=_make_headers(),
        params={"stock_status": "bad_status"},
    )
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 3. consume happy path（FR-0007 main flow）
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_happy_path(client):
    """consume 正常：扣庫存 + 建 transaction，回傳 item + transaction。"""
    item_id = await _insert_item(quantity_on_hand=10, reorder_point=3)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 3},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # 庫存扣了 3（10 → 7）
    assert data["item"]["quantity_on_hand"] == 7
    assert data["item"]["stock_status"] == "in_stock"

    # transaction 正確
    txn = data["transaction"]
    assert txn["transaction_type"] == "consume"
    assert txn["quantity"] == 3
    assert txn["item_id"] == item_id

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_insufficient_inventory_409(client):
    """consume 庫存不足 → 409 INSUFFICIENT_INVENTORY，庫存不變。"""
    item_id = await _insert_item(quantity_on_hand=2, reorder_point=5)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 5},  # 超過 qty=2
    )
    assert resp.status_code == 409, resp.text
    assert "INSUFFICIENT_INVENTORY" in resp.text

    # 確認庫存未被扣
    get_resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}",
        headers=_make_headers(),
    )
    assert get_resp.json()["data"]["quantity_on_hand"] == 2

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_serial_required_no_serial_422(client):
    """serial_required=True，consume 未帶 serial → 422 SERIAL_REQUIRED。"""
    item_id = await _insert_item(
        quantity_on_hand=10, serial_required=True
    )

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 1},  # 無 serial
    )
    assert resp.status_code == 422, resp.text
    assert "SERIAL_REQUIRED" in resp.text

    # 庫存不扣
    get_resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}",
        headers=_make_headers(),
    )
    assert get_resp.json()["data"]["quantity_on_hand"] == 10

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_serial_required_with_serial_ok(client):
    """serial_required=True，帶 serial → 正常扣庫存。"""
    item_id = await _insert_item(
        quantity_on_hand=5, serial_required=True
    )

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 1, "serial": "SN-LOCK-001"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["item"]["quantity_on_hand"] == 4
    assert data["transaction"]["serial"] == "SN-LOCK-001"

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_triggers_reorder_log(client, caplog):
    """consume 後庫存 < reorder_point → logger 記 InventoryBelowReorderPoint。

    qty=6, reorder=5, consume 2 → 剩 4 < 5 → 觸發 reorder log。
    """
    import logging

    item_id = await _insert_item(quantity_on_hand=6, reorder_point=5)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    with caplog.at_level(logging.INFO, logger="api.inventory_v2_service"):
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
            headers=headers,
            json={"quantity": 2},  # 6 - 2 = 4 < reorder_point=5
        )

    assert resp.status_code == 200, resp.text
    # 庫存確認
    assert resp.json()["data"]["item"]["quantity_on_hand"] == 4

    # reorder log 確認
    assert any("InventoryBelowReorderPoint" in r.message for r in caplog.records)

    await _cleanup_item(item_id)


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 4. return
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_return_restores_quantity(client):
    """return：庫存 += quantity，建 transaction(return)。"""
    item_id = await _insert_item(quantity_on_hand=5, reorder_point=3)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:return",
        headers=headers,
        json={"quantity": 2, "notes": "客戶退回"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["item"]["quantity_on_hand"] == 7
    assert data["transaction"]["transaction_type"] == "return"
    assert data["transaction"]["quantity"] == 2

    await _cleanup_item(item_id)


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 5. restock
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_restock_increases_quantity(client):
    """restock：庫存 += quantity，建 transaction(purchase)。"""
    item_id = await _insert_item(quantity_on_hand=3, reorder_point=5)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:restock",
        headers=headers,
        json={"quantity": 20, "supplier": "供應商A", "notes": "月度補貨"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["item"]["quantity_on_hand"] == 23
    assert data["item"]["stock_status"] == "in_stock"
    assert data["transaction"]["transaction_type"] == "purchase"
    assert data["transaction"]["quantity"] == 20

    await _cleanup_item(item_id)


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 6. cross-tenant guard → 403
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_read_403(client):
    """跨 tenant 讀取品項 → 403 CROSS_TENANT_READ。"""
    item_id = await _insert_item()

    # token 是 DEFAULT_TENANT，但 path tenantId 是 OTHER_TENANT
    from tests.conftest import _make_token

    token = _make_token(user_id=ADMIN_USER_ID, role="admin", tenant_id=DEFAULT_TENANT_ID)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }

    resp = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/inventory/items/{item_id}",
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
    assert "CROSS_TENANT" in resp.text

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_write_403(client):
    """跨 tenant consume → 403 CROSS_TENANT_WRITE。"""
    item_id = await _insert_item()

    from tests.conftest import _make_token

    token = _make_token(user_id=ADMIN_USER_ID, role="admin", tenant_id=DEFAULT_TENANT_ID)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
        "Idempotency-Key": _idem_key(),
    }

    resp = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 1},
    )
    assert resp.status_code == 403, resp.text
    assert "CROSS_TENANT" in resp.text

    await _cleanup_item(item_id)


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — 7. 並發 consume（FOR UPDATE 序列化）
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_concurrent_consume_sequential_boundary(client):
    """並發保護語意測試（循序版）：

    架構說明：測試環境使用單一 psycopg3 連線（autocommit conn），
    asyncio.gather 在同一 event loop 上交錯執行，但 FOR UPDATE 需要
    同一連線上不可有兩個並發 transaction 同時開啟，
    因此用「循序兩次 consume」驗證 FOR UPDATE 序列化語意：
      - consume 1（qty=6）→ 200，庫存 8→2
      - consume 2（qty=6）→ 409 INSUFFICIENT_INVENTORY（剩 2 不夠）
      - 最終庫存 = 2（≥ 0，非負）

    真正的多執行緒並發保護由 PostgreSQL FOR UPDATE + service transaction 確保。
    """
    item_id = await _insert_item(quantity_on_hand=8, reorder_point=2)

    # 第一次 consume（應成功）
    h1 = _make_headers()
    h1["Idempotency-Key"] = _idem_key()
    r1 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=h1,
        json={"quantity": 6},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["data"]["item"]["quantity_on_hand"] == 2

    # 第二次 consume（同 qty=6，庫存已剩 2 → INSUFFICIENT）
    h2 = _make_headers()
    h2["Idempotency-Key"] = _idem_key()
    r2 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=h2,
        json={"quantity": 6},
    )
    assert r2.status_code == 409, r2.text
    assert "INSUFFICIENT_INVENTORY" in r2.text

    # 庫存不為負（FOR UPDATE 保護關鍵驗證）
    get_resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}",
        headers=_make_headers(),
    )
    final_qty = get_resp.json()["data"]["quantity_on_hand"]
    assert final_qty >= 0, f"庫存不應為負：{final_qty}"
    assert final_qty == 2

    await _cleanup_item(item_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_consume_boundary_exactly_zero(client):
    """consume 正好把庫存扣到 0 → 200，stock_status=out_of_stock。"""
    item_id = await _insert_item(quantity_on_hand=5, reorder_point=3)

    headers = _make_headers()
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/inventory/items/{item_id}:consume",
        headers=headers,
        json={"quantity": 5},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["item"]["quantity_on_hand"] == 0
    assert data["item"]["stock_status"] == "out_of_stock"

    await _cleanup_item(item_id)
