"""Dispute v2 endpoint tests (FR-0013 / CR-0004 §8 Track B S2).

@pytest.mark.component — 需 live DB（saas.dispute / saas.tenant）
@pytest.mark.unit     — 純邏輯（decimal coerce / evidence coerce / status 常數）

測資策略：
  - 每個 component test 自建 saas.dispute row（INSERT 直打 DB）
  - tenant = DEFAULT_TENANT_ID（00000000-…-0001，migration 004 已 seed saas.tenant）
  - filed_by 使用任意 uuid（saas.dispute.filed_by 無 FK constraint，spec HD-1 D-C5 設計）
  - 測試後 cleanup（DELETE by id）確保隔離
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID

# CSM reviewer UUID（fake，無 DB FK 要求）
CSM_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
# ops_manager co-signer UUID（不同於 CSM）
OPS_USER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
# filed_by（任意 UUID，無 FK constraint）
FILED_BY_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic, no DB
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDecimalCoerce:
    def test_none_returns_none(self):
        from services.dispute_v2_service import _coerce_decimal
        assert _coerce_decimal(None) is None

    def test_integer_rounds_to_two_decimal(self):
        from services.dispute_v2_service import _coerce_decimal
        assert _coerce_decimal(100) == "100.00"

    def test_float_precision(self):
        from services.dispute_v2_service import _coerce_decimal
        assert _coerce_decimal(1234.5) == "1234.50"

    def test_negative_amount(self):
        from services.dispute_v2_service import _coerce_decimal
        assert _coerce_decimal(-500.0) == "-500.00"

    def test_string_numeric(self):
        from services.dispute_v2_service import _coerce_decimal
        assert _coerce_decimal("99.99") == "99.99"


@pytest.mark.unit
class TestEvidenceCoerce:
    def test_none_returns_none(self):
        from services.dispute_v2_service import _coerce_evidence
        assert _coerce_evidence(None) is None

    def test_dict_passthrough(self):
        from services.dispute_v2_service import _coerce_evidence
        d = {"url": "https://example.com/photo.jpg"}
        assert _coerce_evidence(d) == d

    def test_list_passthrough(self):
        from services.dispute_v2_service import _coerce_evidence
        lst = [{"url": "a"}, {"url": "b"}]
        assert _coerce_evidence(lst) == lst

    def test_json_string_parsed(self):
        from services.dispute_v2_service import _coerce_evidence
        result = _coerce_evidence('{"key": "val"}')
        assert result == {"key": "val"}

    def test_invalid_string_returns_none(self):
        from services.dispute_v2_service import _coerce_evidence
        assert _coerce_evidence("not-json") is None


@pytest.mark.unit
class TestValidStatusSet:
    def test_all_canonical_statuses_present(self):
        from services.dispute_v2_service import _VALID_STATUS
        expected = {
            "filed", "in_review", "mediation",
            "resolved", "escalated", "closed_withdrawn",
        }
        assert expected == _VALID_STATUS

    def test_valid_dispute_types(self):
        from services.dispute_v2_service import _VALID_DISPUTE_TYPE
        expected = {"pricing", "quality", "warranty", "cancellation_fee", "settlement"}
        assert expected == _VALID_DISPUTE_TYPE


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for component tests
# ─────────────────────────────────────────────────────────────────────────────

async def _insert_dispute(
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    filed_by: str = FILED_BY_ID,
    dispute_type: str = "quality",
    status: str = "filed",
    reviewed_by: str | None = None,
    cosigned_by: str | None = None,
    work_order_id: str | None = None,
    invoice_id: str | None = None,
    description: str = "測試爭議描述",
) -> str:
    """直接 INSERT 一筆 saas.dispute，回傳 id。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    dispute_id = str(uuid.uuid4())

    # 動態建 SQL：視 reviewed_by / cosigned_by 決定欄位
    reviewed_sql = ""
    cosigned_sql = ""
    extra_cols = ""
    extra_vals = ""

    if reviewed_by:
        extra_cols += ", reviewed_by, reviewed_at"
        extra_vals += f", '{reviewed_by}'::uuid, NOW()"
        # 只有 reviewed_by 時預設 in_review
        if status == "filed" and not cosigned_by:
            status = "in_review"

    if cosigned_by:
        extra_cols += ", cosigned_by, cosigned_at"
        extra_vals += f", '{cosigned_by}'::uuid, NOW()"
        # 同時有兩個 signer 時預設 resolved
        if status in ("filed", "in_review"):
            status = "resolved"

    wo_val = f"'{work_order_id}'::uuid" if work_order_id else "NULL"
    inv_val = f"'{invoice_id}'::uuid" if invoice_id else "NULL"

    await db_module._conn.execute(
        f"INSERT INTO saas.dispute "
        f"  (id, tenant_id, work_order_id, invoice_id, filed_by, dispute_type, "
        f"   status, description, filed_at, sla_deadline{extra_cols}) "
        f"VALUES "
        f"  (%s::uuid, %s::uuid, {wo_val}, {inv_val}, %s::uuid, %s, "
        f"   %s, %s, NOW(), NOW() + INTERVAL '60 days'{extra_vals})",
        (dispute_id, tenant_id, filed_by, dispute_type, status, description),
    )
    return dispute_id


async def _cleanup(dispute_id: str) -> None:
    """刪 dispute（cleanup，避免污染其他 test）。

    先刪 child disputes（parent_dispute_id FK），再刪本身。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    # 先遞迴刪子 disputes（reopen lineage）
    await db_module._conn.execute(
        "DELETE FROM saas.dispute WHERE parent_dispute_id = %s::uuid",
        (dispute_id,),
    )
    await db_module._conn.execute(
        "DELETE FROM saas.dispute WHERE id = %s::uuid",
        (dispute_id,),
    )


def _make_headers(
    user_id: str,
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
    """每次產生唯一的 idempotency key（POST 必填）。"""
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Component tests
# ─────────────────────────────────────────────────────────────────────────────

# ---------- 1. open → filed -------------------------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_open_dispute_returns_filed(client):
    """POST /disputes → 201, status=filed。"""
    headers = _make_headers(ADMIN_USER_ID)
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/disputes",
        headers=headers,
        json={
            "filed_by": FILED_BY_ID,
            "dispute_type": "quality",
            "description": "品質問題",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "filed"
    assert data["dispute_type"] == "quality"
    assert data["filed_by"] == FILED_BY_ID
    assert data["sla_deadline"] is not None

    # cleanup
    await _cleanup(data["id"])


@pytest.mark.component
@pytest.mark.asyncio
async def test_open_dispute_invalid_type_422(client):
    """POST /disputes 帶不合法 dispute_type → 422。"""
    headers = _make_headers(ADMIN_USER_ID)
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/disputes",
        headers=headers,
        json={
            "filed_by": FILED_BY_ID,
            "dispute_type": "invalid_type",
        },
    )
    assert resp.status_code == 422


# ---------- 2. review filed → in_review ------------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_review_filed_to_in_review(client):
    """review：filed → in_review（step-1 CSM）。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:review",
            headers=headers,
            json={"proposed_resolution": "CSM 審查提案解決方案", "to_mediation": False},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "in_review"
        assert data["reviewed_by"] == CSM_USER_ID
        assert data["reviewed_at"] is not None
        assert data["proposed_resolution"] == "CSM 審查提案解決方案"
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_review_filed_to_mediation(client):
    """review to_mediation=True：filed → mediation。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:review",
            headers=headers,
            json={"proposed_resolution": "轉仲裁", "to_mediation": True},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "mediation"
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_review_non_filed_409(client):
    """review 非 filed（in_review）→ 409 STATE_CONFLICT。"""
    dispute_id = await _insert_dispute(reviewed_by=CSM_USER_ID)  # status=in_review
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:review",
            headers=headers,
            json={"proposed_resolution": "再次 review"},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "STATE_CONFLICT"
    finally:
        await _cleanup(dispute_id)


# ---------- 3. co-sign in_review → resolved --------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_in_review_to_resolved(client):
    """co-sign：in_review → resolved（SoD 兩人相異）。"""
    dispute_id = await _insert_dispute(reviewed_by=CSM_USER_ID)  # status=in_review
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = OPS_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:co-sign",
            headers=headers,
            json={"resolution": "客訴成立，退款 2000 元"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "resolved"
        assert data["cosigned_by"] == OPS_USER_ID
        assert data["cosigned_at"] is not None
        assert data["resolved_at"] is not None
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_without_review_409_dual_sign_required(client):
    """co-sign 對 filed（未 review）→ 409 DUAL_SIGN_REQUIRED。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = OPS_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:co-sign",
            headers=headers,
            json={"resolution": "未經 review 就 co-sign"},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "DUAL_SIGN_REQUIRED"
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_same_person_as_reviewer_403_sod_violation(client):
    """co-sign 與 review 同一人 → 403 SOD_VIOLATION。"""
    dispute_id = await _insert_dispute(reviewed_by=CSM_USER_ID)  # status=in_review
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID  # 與 reviewed_by 相同 → SOD_VIOLATION
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:co-sign",
            headers=headers,
            json={"resolution": "同一人兩簽"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SOD_VIOLATION"
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_co_sign_resolution_too_short_422(client):
    """co-sign resolution 不足 5 字 → 422。"""
    dispute_id = await _insert_dispute(reviewed_by=CSM_USER_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = OPS_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:co-sign",
            headers=headers,
            json={"resolution": "短"},
        )
        assert resp.status_code == 422
    finally:
        await _cleanup(dispute_id)


# ---------- 4. withdraw → closed_withdrawn ---------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_withdraw_filed_to_closed_withdrawn(client):
    """withdraw：filed → closed_withdrawn。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:withdraw",
            headers=headers,
            json={"reason": "客戶自行撤銷"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "closed_withdrawn"
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_withdraw_resolved_409(client):
    """withdraw 已 resolved → 409 STATE_CONFLICT。"""
    dispute_id = await _insert_dispute(reviewed_by=CSM_USER_ID, cosigned_by=OPS_USER_ID)  # status=resolved
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:withdraw",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "STATE_CONFLICT"
    finally:
        await _cleanup(dispute_id)


# ---------- 5. escalate → escalated -----------------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_escalate_filed_to_escalated(client):
    """escalate：filed → escalated, escalated_to='ops_director'。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["X-Initiator"] = CSM_USER_ID
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:escalate",
            headers=headers,
            json={"reason": "超出 CSM 處理範圍"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "escalated"
        assert data["escalated_to"] == "ops_director"
        assert data["escalated_at"] is not None
    finally:
        await _cleanup(dispute_id)


# ---------- 6. reopen: resolved → 新 dispute w/ parent ---------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_reopen_resolved_creates_new_dispute_with_parent(client):
    """reopen resolved → 201 新 dispute, status=filed, parent_dispute_id=原 id。"""
    # 建一筆 resolved dispute
    orig_id = await _insert_dispute(reviewed_by=CSM_USER_ID, cosigned_by=OPS_USER_ID)
    new_id = None
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{orig_id}:reopen",
            headers=headers,
            json={"description": "問題未真正解決，重新申訴"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        new_id = data["id"]

        assert data["status"] == "filed"
        assert data["parent_dispute_id"] == orig_id
        assert data["description"] == "問題未真正解決，重新申訴"
        # 繼承原 dispute 的 dispute_type
        assert data["dispute_type"] == "quality"
    finally:
        if new_id:
            await _cleanup(new_id)
        await _cleanup(orig_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_reopen_unfiled_dispute_409(client):
    """reopen 非 resolved/closed_withdrawn → 409 STATE_CONFLICT。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()

        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}:reopen",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "STATE_CONFLICT"
    finally:
        await _cleanup(dispute_id)


# ---------- 7. cross-tenant guard ------------------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_list_403(client):
    """cross-tenant GET list → 403 CROSS_TENANT_READ。"""
    other_tenant_id = "99999999-9999-9999-9999-999999999999"
    headers = _make_headers(ADMIN_USER_ID)  # token 的 tenant = DEFAULT_TENANT_ID

    resp = await client.get(
        f"/tenants/{other_tenant_id}/disputes",
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] in ("CROSS_TENANT_READ", "TENANT_MISMATCH")


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_open_403(client):
    """cross-tenant POST open → 403 CROSS_TENANT_WRITE。"""
    other_tenant_id = "99999999-9999-9999-9999-999999999999"
    headers = _make_headers(ADMIN_USER_ID)
    headers["Idempotency-Key"] = _idem_key()

    resp = await client.post(
        f"/tenants/{other_tenant_id}/disputes",
        headers=headers,
        json={"filed_by": FILED_BY_ID, "dispute_type": "quality"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] in ("CROSS_TENANT_WRITE", "TENANT_MISMATCH")


# ---------- 8. list / get --------------------------------------------------

@pytest.mark.component
@pytest.mark.asyncio
async def test_list_disputes_returns_created_row(client):
    """list 正常回傳（有測資）。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes",
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert dispute_id in ids
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_dispute_success(client):
    """單筆查詢成功。"""
    dispute_id = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes/{dispute_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == dispute_id
        assert data["status"] == "filed"
        assert data["tenant_id"] == DEFAULT_TENANT_ID
    finally:
        await _cleanup(dispute_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_dispute_404(client):
    """不存在的 id → 404 NOT_FOUND。"""
    headers = _make_headers(ADMIN_USER_ID)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/disputes/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "NOT_FOUND"


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_status_filter(client):
    """status filter 正常運作。"""
    id_filed = await _insert_dispute(status="filed")
    id_resolved = await _insert_dispute(reviewed_by=CSM_USER_ID, cosigned_by=OPS_USER_ID)  # resolved
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes?status=filed",
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert id_filed in ids
        assert id_resolved not in ids
    finally:
        await _cleanup(id_filed)
        await _cleanup(id_resolved)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_pagination(client):
    """limit=1 → has_more=True（若有 2+ rows）。"""
    id1 = await _insert_dispute(status="filed")
    id2 = await _insert_dispute(status="filed")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/disputes?limit=1",
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
