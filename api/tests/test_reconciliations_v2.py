"""Reconciliation v2 endpoint tests (FR-0013 / CR-0004 §8 Track B S2).

@pytest.mark.component — 需 live DB（saas.reconciliation / saas.settlement / saas.tenant）
@pytest.mark.unit     — 純邏輯（decimal coerce / status 常數）

測資策略：
  - 每個 component test 自建 saas.reconciliation pending row（INSERT 直打 DB）
  - tenant = DEFAULT_TENANT_ID（00000000-…-0001，migration 004 已 seed saas.tenant）
  - technician_id 使用任意 uuid（saas.reconciliation.technician_id 無 FK 強制）
  - 測試後 cleanup（DELETE by id）確保隔離
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID, CUSTOMER_SERVICE_USER_ID

# CSM reviewer UUID（fake，無 DB FK 要求）
CSM_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
# ops_manager co-signer UUID（不同於 CSM）
OPS_USER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

TECH_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic, no DB
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDecimalCoerce:
    def test_none_returns_zero(self):
        from services.reconciliation_v2_service import _coerce_decimal
        assert _coerce_decimal(None) == "0.00"

    def test_integer_rounds_to_two_decimal(self):
        from services.reconciliation_v2_service import _coerce_decimal
        assert _coerce_decimal(100) == "100.00"

    def test_float_precision(self):
        from services.reconciliation_v2_service import _coerce_decimal
        assert _coerce_decimal(1234.5) == "1234.50"

    def test_string_numeric(self):
        from services.reconciliation_v2_service import _coerce_decimal
        assert _coerce_decimal("99.99") == "99.99"


@pytest.mark.unit
class TestValidStatusSet:
    def test_valid_statuses_defined(self):
        from services.reconciliation_v2_service import _VALID_STATUS
        assert "pending" in _VALID_STATUS
        assert "in_review" in _VALID_STATUS
        assert "approved" in _VALID_STATUS
        assert "disputed" in _VALID_STATUS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for component tests
# ─────────────────────────────────────────────────────────────────────────────

async def _insert_reconciliation(
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    technician_id: str = TECH_ID,
    status: str = "pending",
    reviewed_by: str | None = None,
    reviewed_at_sql: str = "NULL",
    total_orders: int = 3,
    total_revenue: float = 3000.0,
    platform_fee: float = 300.0,
    technician_payout: float = 2700.0,
) -> str:
    """直接 INSERT 一筆 saas.reconciliation，回傳 id。"""
    import core.db as db_module
    from core.db import _ensure_conn
    await _ensure_conn()
    recon_id = str(uuid.uuid4())

    reviewed_by_val = f"'{reviewed_by}'::uuid" if reviewed_by else "NULL"
    reviewed_at_val = "NOW()" if reviewed_by else "NULL"
    status_val_for_reviewed = "in_review" if reviewed_by else status

    await db_module._conn.execute(
        "INSERT INTO saas.reconciliation "
        "  (id, tenant_id, technician_id, period_start, period_end, total_orders, "
        "   total_revenue, platform_fee, technician_payout, status, reviewed_by, reviewed_at) "
        "VALUES "
        "  (%s::uuid, %s::uuid, %s::uuid, NOW()-INTERVAL '30 days', NOW()-INTERVAL '1 day', "
        "   %s, %s, %s, %s, %s, "
        f"  {reviewed_by_val}, {reviewed_at_val})",
        (recon_id, tenant_id, technician_id, total_orders,
         total_revenue, platform_fee, technician_payout, status_val_for_reviewed),
    )
    return recon_id


async def _cleanup(recon_id: str) -> None:
    """刪 settlement + reconciliation（cleanup，避免污染其他 test）。"""
    import core.db as db_module
    from core.db import _ensure_conn
    await _ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM saas.settlement WHERE reconciliation_id = %s::uuid",
        (recon_id,),
    )
    await db_module._conn.execute(
        "DELETE FROM saas.reconciliation WHERE id = %s::uuid",
        (recon_id,),
    )


def _make_headers(user_id: str, role: str = "admin", tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    from tests.conftest import _make_token
    token = _make_token(user_id=user_id, role=role, tenant_id=tenant_id)
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


def _idem_key() -> str:
    """每次產生唯一的 idempotency key（POST 必填）。"""
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Component tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_list_reconciliations_empty(client):
    """空 list（tenant 有 0 rows 或 filter 不符）。"""
    headers = _make_headers(ADMIN_USER_ID)
    # 用不存在的 technician_id 確保空回傳
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations"
        f"?technician_id=ffffffff-ffff-ffff-ffff-ffffffffffff",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "has_more" in body
    assert isinstance(body["items"], list)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_reconciliations_with_data(client):
    """list 正常回傳（有測資）。"""
    recon_id = await _insert_reconciliation()
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["id"] for item in body["items"]]
        assert recon_id in ids
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_reconciliations_pagination(client):
    """limit=1 → has_more=True（若有 2+ rows）。"""
    id1 = await _insert_reconciliation()
    id2 = await _insert_reconciliation()
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations?limit=1",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["has_more"] is True
        assert body["next_cursor"] is not None
    finally:
        await _cleanup(id1)
        await _cleanup(id2)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_reconciliation_404(client):
    """不存在的 id → 404 NOT_FOUND。"""
    headers = _make_headers(ADMIN_USER_ID)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "NOT_FOUND"


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_reconciliation_success(client):
    """單筆查詢成功。"""
    recon_id = await _insert_reconciliation()
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == recon_id
        assert body["data"]["status"] == "pending"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_review_pending_to_in_review(client):
    """review：pending → in_review（step-1 CSM）。"""
    recon_id = await _insert_reconciliation(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:review",
            headers=headers,
            json={"note": "CSM 確認無誤"},
        )
        assert resp.status_code == 200
        body = resp.json()
        recon = body["data"]
        assert recon["status"] == "in_review"
        assert recon["reviewed_by"] == CSM_USER_ID
        assert recon["reviewed_at"] is not None
        assert recon["note"] == "CSM 確認無誤"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_review_non_pending_409(client):
    """review 非 pending → 409 STATE_CONFLICT。"""
    # 直接建一筆 in_review 狀態的 row
    recon_id = await _insert_reconciliation(reviewed_by=CSM_USER_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:review",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "STATE_CONFLICT"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_in_review_to_approved_with_settlement(client):
    """co-sign：in_review → approved + saas.settlement 建立。"""
    recon_id = await _insert_reconciliation(reviewed_by=CSM_USER_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = OPS_USER_ID  # 不同於 CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:co-sign",
            headers=headers,
            json={"note": "ops 確認"},
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        recon = data["reconciliation"]
        settlement = data["settlement"]
        # reconciliation
        assert recon["status"] == "approved"
        assert recon["approved_by"] == OPS_USER_ID
        assert recon["approved_at"] is not None
        # settlement
        assert settlement["reconciliation_id"] == recon_id
        assert settlement["technician_id"] == TECH_ID
        assert settlement["amount"] == "2700.00"
        assert settlement["currency"] == "TWD"
        assert settlement["status"] == "pending"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_without_review_409_dual_sign_required(client):
    """co-sign 對 pending（未 review）→ 409 DUAL_SIGN_REQUIRED。"""
    recon_id = await _insert_reconciliation(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = OPS_USER_ID
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:co-sign",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "DUAL_SIGN_REQUIRED"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_same_person_as_reviewer_403_sod_violation(client):
    """co-sign 與 review 同一人 → 403 SOD_VIOLATION。"""
    recon_id = await _insert_reconciliation(reviewed_by=CSM_USER_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID  # 與 reviewed_by 相同 → SOD_VIOLATION
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:co-sign",
            headers=headers,
            json={},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SOD_VIOLATION"
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_get_403(client):
    """cross-tenant GET → 403 CROSS_TENANT_READ 或 TENANT_MISMATCH。"""
    other_tenant_id = "99999999-9999-9999-9999-999999999999"
    # token tenant = DEFAULT_TENANT_ID，path tenant = other_tenant_id
    headers = _make_headers(ADMIN_USER_ID)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/tenants/{other_tenant_id}/accounting/reconciliations/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] in ("CROSS_TENANT_READ", "TENANT_MISMATCH")


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_review_403(client):
    """cross-tenant :review → 403 CROSS_TENANT_WRITE 或 TENANT_MISMATCH。"""
    other_tenant_id = "99999999-9999-9999-9999-999999999999"
    headers = _make_headers(ADMIN_USER_ID)
    headers["X-Initiator"] = CSM_USER_ID
    headers["Idempotency-Key"] = _idem_key()
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/tenants/{other_tenant_id}/accounting/reconciliations/{fake_id}:review",
        headers=headers,
        json={},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] in ("CROSS_TENANT_WRITE", "TENANT_MISMATCH")


@pytest.mark.component
@pytest.mark.asyncio
async def test_review_missing_initiator_header_422(client):
    """review 缺 X-Initiator → 422 VALIDATION_ERROR。"""
    recon_id = await _insert_reconciliation(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        # 不加 X-Initiator
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations/{recon_id}:review",
            headers=headers,
            json={},
        )
        assert resp.status_code == 422
    finally:
        await _cleanup(recon_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_status_filter(client):
    """status filter 正常運作——pending row 出現，approved row 過濾掉。"""
    id_pending = await _insert_reconciliation(status="pending")
    id_reviewed = await _insert_reconciliation(reviewed_by=CSM_USER_ID)  # in_review
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/accounting/reconciliations?status=pending",
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert id_pending in ids
        assert id_reviewed not in ids
    finally:
        await _cleanup(id_pending)
        await _cleanup(id_reviewed)
