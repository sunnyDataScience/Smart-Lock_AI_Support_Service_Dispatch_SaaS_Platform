"""Pricing Rules v2 endpoint tests（Track B S4 / CR-0004 §8 C3 / ADR-0046）。

@pytest.mark.component — 需 live DB（saas.price_rule / saas.change_request / saas.tenant）
@pytest.mark.unit     — 純邏輯（decimal coerce / surcharges 正規化）

測資策略：
  - 每個 component test 自建 saas.price_rule row（INSERT 直打 DB 或透過 POST endpoint）
  - tenant = DEFAULT_TENANT_ID（00000000-…-0001，migration 004 已 seed saas.tenant）
  - 測試後 cleanup（DELETE by id）確保隔離
  - X-Initiator header 使用 ADMIN_USER_ID（fake uuid，無 FK 要求）
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID

# 第二個 tenant（cross-tenant guard 測試用）
OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# X-Initiator 使用 admin user id（fake uuid，無 FK）
INITIATOR_ID = ADMIN_USER_ID


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic, no DB
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDecimalCoerceV2:
    def test_none_returns_zero(self):
        from services.pricing_rule_v2_service import _coerce_decimal
        assert _coerce_decimal(None) == "0.00"

    def test_integer_rounds_to_two_decimal(self):
        from services.pricing_rule_v2_service import _coerce_decimal
        assert _coerce_decimal(100) == "100.00"

    def test_float_precision(self):
        from services.pricing_rule_v2_service import _coerce_decimal
        assert _coerce_decimal(1234.5) == "1234.50"

    def test_string_numeric(self):
        from services.pricing_rule_v2_service import _coerce_decimal
        assert _coerce_decimal("99.99") == "99.99"


@pytest.mark.unit
class TestDecimalValidation:
    def test_valid_string_accepted(self):
        from services.pricing_rule_v2_service import _validate_decimal_str
        assert _validate_decimal_str("1200.00", "base_price") == 1200.0

    def test_valid_number_accepted(self):
        from services.pricing_rule_v2_service import _validate_decimal_str
        assert _validate_decimal_str(500, "base_price") == 500.0

    def test_invalid_string_raises(self):
        from core.errors import ApiError
        from services.pricing_rule_v2_service import _validate_decimal_str
        with pytest.raises(ApiError) as exc:
            _validate_decimal_str("abc", "base_price")
        assert exc.value.status_code == 422

    def test_negative_raises(self):
        from core.errors import ApiError
        from services.pricing_rule_v2_service import _validate_decimal_str
        with pytest.raises(ApiError) as exc:
            _validate_decimal_str(-1, "base_price")
        assert exc.value.status_code == 422

    def test_none_raises(self):
        from core.errors import ApiError
        from services.pricing_rule_v2_service import _validate_decimal_str
        with pytest.raises(ApiError) as exc:
            _validate_decimal_str(None, "base_price")
        assert exc.value.status_code == 422


@pytest.mark.unit
class TestSurchargesNormalization:
    def test_none_returns_empty(self):
        from services.pricing_rule_v2_service import _normalize_surcharges_output
        assert _normalize_surcharges_output(None) == []

    def test_list_format_parsed(self):
        from services.pricing_rule_v2_service import _normalize_surcharges_output
        modifiers = [{"name": "夜間加價", "amount": 200.0, "condition": "night"}]
        result = _normalize_surcharges_output(modifiers)
        assert len(result) == 1
        assert result[0]["name"] == "夜間加價"
        assert result[0]["amount"] == "200.00"
        assert result[0]["condition"] == "night"

    def test_dict_format_parsed(self):
        from services.pricing_rule_v2_service import _normalize_surcharges_output
        modifiers = {"緊急服務": {"amount": 500.0}}
        result = _normalize_surcharges_output(modifiers)
        assert len(result) == 1
        assert result[0]["name"] == "緊急服務"
        assert result[0]["amount"] == "500.00"

    def test_input_normalization_valid(self):
        from services.pricing_rule_v2_service import _normalize_surcharges_input
        surcharges = [{"name": "加班費", "amount": "100.00", "condition": "overtime"}]
        result = _normalize_surcharges_input(surcharges)
        assert len(result) == 1
        assert result[0]["name"] == "加班費"
        assert result[0]["amount"] == 100.0

    def test_input_missing_name_raises(self):
        from core.errors import ApiError
        from services.pricing_rule_v2_service import _normalize_surcharges_input
        with pytest.raises(ApiError) as exc:
            _normalize_surcharges_input([{"amount": "100.00"}])
        assert exc.value.status_code == 422

    def test_input_not_array_raises(self):
        from core.errors import ApiError
        from services.pricing_rule_v2_service import _normalize_surcharges_input
        with pytest.raises(ApiError) as exc:
            _normalize_surcharges_input("not-an-array")
        assert exc.value.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for component tests
# ─────────────────────────────────────────────────────────────────────────────


def _make_headers(
    user_id: str = INITIATOR_ID,
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
    initiator_id: str | None = None,
    idem_key: str | None = None,
) -> dict:
    from tests.conftest import _make_token
    token = _make_token(user_id=user_id, role=role, tenant_id=tenant_id)
    h = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }
    if initiator_id:
        h["X-Initiator"] = initiator_id
    if idem_key:
        h["Idempotency-Key"] = idem_key
    return h


def _idem_key() -> str:
    return str(uuid.uuid4())


async def _cleanup_rule(rule_id: str) -> None:
    """刪 change_request + price_rule（cleanup，避免污染其他 test）。"""
    import core.db as db_module
    from core.db import _ensure_conn
    await _ensure_conn()
    # 先刪 change_request（payload_diff 中包含 rule id）
    # 用 payload_diff 中的 after.id 匹配（最可靠）
    await db_module._conn.execute(
        "DELETE FROM saas.change_request "
        "WHERE (payload_diff->'after'->>'id' = %s "
        "   OR payload_diff->'before'->>'id' = %s) "
        "  AND type_code = 'pricing_rule'",
        (rule_id, rule_id),
    )
    await db_module._conn.execute(
        "DELETE FROM saas.price_rule WHERE id = %s::uuid",
        (rule_id,),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Component tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_pricing_rule_and_change_request(client):
    """POST create → 201；驗 change_request 有寫一筆 type_code=pricing_rule。"""
    rule_id = None
    try:
        headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "TestBrand",
                "lock_type": "smart_lock",
                "difficulty": "easy",
                "base_price": "1200.00",
                "labor_cost": "200.00",
                "reason": "unit test create",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["data"]["brand"] == "TestBrand"
        assert data["data"]["base_price"] == "1200.00"
        assert data["data"]["labor_cost"] == "200.00"
        assert data["data"]["is_active"] is True
        rule_id = data["data"]["id"]

        # 驗 change_request 有寫一筆 type_code=pricing_rule
        import core.db as db_module
        from core.db import _ensure_conn
        await _ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT id, type_code, state, payload_diff->>'action' as action, "
            "       created_by "
            "FROM saas.change_request "
            "WHERE payload_diff->'after'->>'id' = %s "
            "  AND type_code = 'pricing_rule'",
            (rule_id,),
        )
        cr = await cur.fetchone()
        assert cr is not None, "change_request not written for create"
        assert cr[1] == "pricing_rule"
        assert cr[2] == "effective"
        assert cr[3] == "create"
        assert str(cr[4]) == INITIATOR_ID
    finally:
        if rule_id:
            await _cleanup_rule(rule_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_pricing_rule_404(client):
    """GET 不存在的 rule → 404 NOT_FOUND。"""
    fake_id = str(uuid.uuid4())
    headers = _make_headers()
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error_code") == "NOT_FOUND"


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_pricing_rules_brand_filter(client):
    """POST 兩筆不同 brand → GET list 用 brand filter 只回傳對的那筆。"""
    rule_a_id = None
    rule_b_id = None
    try:
        headers_a = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp_a = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "BrandAlpha",
                "lock_type": "digital_deadbolt",
                "base_price": 800,
                "reason": "test brand filter A",
            },
            headers=headers_a,
        )
        assert resp_a.status_code == 201, resp_a.text
        rule_a_id = resp_a.json()["data"]["id"]

        headers_b = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp_b = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "BrandBeta",
                "lock_type": "digital_deadbolt",
                "base_price": 900,
                "reason": "test brand filter B",
            },
            headers=headers_b,
        )
        assert resp_b.status_code == 201, resp_b.text
        rule_b_id = resp_b.json()["data"]["id"]

        # Filter by BrandAlpha（大小寫不敏感）
        list_headers = _make_headers()
        resp_list = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules?brand=brandalpha",
            headers=list_headers,
        )
        assert resp_list.status_code == 200
        items = resp_list.json()["items"]
        ids = [item["id"] for item in items]
        assert rule_a_id in ids
        assert rule_b_id not in ids

        # 確認回傳 decimal 格式正確
        for item in items:
            if item["id"] == rule_a_id:
                assert item["base_price"] == "800.00"
    finally:
        if rule_a_id:
            await _cleanup_rule(rule_a_id)
        if rule_b_id:
            await _cleanup_rule(rule_b_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_update_pricing_rule_and_change_request(client):
    """POST create → PUT update → 驗 change_request action=update + before/after snapshot。"""
    rule_id = None
    try:
        # Create
        create_headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "UpdateBrand",
                "lock_type": "padlock",
                "base_price": "500.00",
                "reason": "test update create",
            },
            headers=create_headers,
        )
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["data"]["id"]

        # Update
        update_headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp_upd = await client.put(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules/{rule_id}",
            json={
                "brand": "UpdateBrand",
                "lock_type": "padlock",
                "base_price": "750.00",
                "labor_cost": "100.00",
                "reason": "price increase",
            },
            headers=update_headers,
        )
        assert resp_upd.status_code == 200, resp_upd.text
        updated = resp_upd.json()["data"]
        assert updated["base_price"] == "750.00"
        assert updated["labor_cost"] == "100.00"

        # 驗 change_request 有 action=update before/after snapshot
        import core.db as db_module
        from core.db import _ensure_conn
        await _ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT payload_diff->>'action' as action, "
            "       payload_diff->'before'->>'base_price' as before_price, "
            "       payload_diff->'after'->>'base_price' as after_price "
            "FROM saas.change_request "
            "WHERE payload_diff->'after'->>'id' = %s "
            "  AND payload_diff->>'action' = 'update' "
            "  AND type_code = 'pricing_rule'",
            (rule_id,),
        )
        cr = await cur.fetchone()
        assert cr is not None, "change_request not written for update"
        assert cr[0] == "update"
        assert cr[1] == "500.00"   # before
        assert cr[2] == "750.00"   # after
    finally:
        if rule_id:
            await _cleanup_rule(rule_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_get_403(client):
    """GET 時 path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_READ。"""
    fake_rule_id = str(uuid.uuid4())
    # Token 是 DEFAULT_TENANT_ID，但 path 用 OTHER_TENANT_ID
    from tests.conftest import _make_token
    token = _make_token(
        user_id=INITIATOR_ID,
        role="admin",
        tenant_id=DEFAULT_TENANT_ID,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }
    resp = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/pricing/rules/{fake_rule_id}",
        headers=headers,
    )
    assert resp.status_code == 403
    body = resp.json()
    assert "CROSS_TENANT" in body.get("error_code", "")


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_post_403(client):
    """POST 時 path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_WRITE。"""
    from tests.conftest import _make_token
    token = _make_token(
        user_id=INITIATOR_ID,
        role="admin",
        tenant_id=DEFAULT_TENANT_ID,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
        "X-Initiator": INITIATOR_ID,
        "Idempotency-Key": _idem_key(),
    }
    resp = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/pricing/rules",
        json={
            "brand": "Hacker",
            "lock_type": "smart_lock",
            "base_price": "100.00",
        },
        headers=headers,
    )
    assert resp.status_code == 403
    body = resp.json()
    assert "CROSS_TENANT" in body.get("error_code", "")


@pytest.mark.component
@pytest.mark.asyncio
async def test_decimal_normalization_output(client):
    """POST → response decimal 欄位均為 2 位小數字串格式。"""
    rule_id = None
    try:
        headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "DecimalBrand",
                "lock_type": "other",
                "base_price": 1500,
                "labor_cost": 300,
                "parts_cost": 50.5,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        rule_id = data["id"]
        assert data["base_price"] == "1500.00"
        assert data["labor_cost"] == "300.00"
        assert data["parts_cost"] == "50.50"
    finally:
        if rule_id:
            await _cleanup_rule(rule_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_missing_x_initiator_422(client):
    """POST 不帶 X-Initiator → 422 VALIDATION_ERROR。"""
    headers = _make_headers()  # 無 initiator_id
    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
        json={
            "brand": "NoBrand",
            "lock_type": "smart_lock",
            "base_price": "100.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.component
@pytest.mark.asyncio
async def test_update_not_found_404(client):
    """PUT 不存在的 rule → 404 NOT_FOUND。"""
    fake_id = str(uuid.uuid4())
    headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
    resp = await client.put(
        f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules/{fake_id}",
        json={
            "brand": "Ghost",
            "lock_type": "smart_lock",
            "base_price": "100.00",
        },
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error_code") == "NOT_FOUND"


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_returns_created_rule(client):
    """POST → GET list 可以查到剛建立的 rule。"""
    rule_id = None
    try:
        headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "ListTestBrand",
                "lock_type": "smart_lock",
                "base_price": "2000.00",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["data"]["id"]

        list_headers = _make_headers()
        resp_list = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            headers=list_headers,
        )
        assert resp_list.status_code == 200
        ids = [item["id"] for item in resp_list.json()["items"]]
        assert rule_id in ids
    finally:
        if rule_id:
            await _cleanup_rule(rule_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_single_rule(client):
    """POST → GET single rule → 200 {data: rule}。"""
    rule_id = None
    try:
        headers = _make_headers(initiator_id=INITIATOR_ID, idem_key=_idem_key())
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules",
            json={
                "brand": "GetSingleBrand",
                "lock_type": "digital_deadbolt",
                "base_price": "3000.00",
                "difficulty": "hard",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["data"]["id"]

        get_headers = _make_headers()
        resp_get = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/pricing/rules/{rule_id}",
            headers=get_headers,
        )
        assert resp_get.status_code == 200
        data = resp_get.json()["data"]
        assert data["id"] == rule_id
        assert data["brand"] == "GetSingleBrand"
        assert data["difficulty"] == "hard"
        assert data["base_price"] == "3000.00"
    finally:
        if rule_id:
            await _cleanup_rule(rule_id)
