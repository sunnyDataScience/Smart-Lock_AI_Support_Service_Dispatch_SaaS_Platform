"""DataCorrections v2 endpoint tests（Track B S5 / CR-0004 §8 / ADR-0029）。

@pytest.mark.component — 需 live DB（public.data_corrections，migration 009 已建）

測資策略：
  - 每個 component test 自建 data_corrections 列（INSERT 直打 DB，帶 tenant_id）
  - DEFAULT_TENANT_ID = 00000000-…-0001（migration 004 已 seed saas.tenant）
  - OTHER_TENANT_ID = 00000000-…-0002（驗 cross-tenant 隔離）
  - correctionId 是 BIGINT（直接用 INSERT RETURNING id）
  - 測試後 DELETE by id 確保隔離
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID, CUSTOMER_SERVICE_USER_ID

# 第二個 tenant（用於 cross-tenant 隔離驗證）
OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000002"

# 非 admin 用戶（customer_service 角色）
CS_USER_ID = CUSTOMER_SERVICE_USER_ID


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _insert_correction(
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    user_id: str = "U_test_line_user",
    note: str = "測試備注",
    status: str = "pending",
) -> int:
    """直接 INSERT 一筆 data_corrections，回傳 id（BIGINT）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "INSERT INTO data_corrections "
        "  (user_id, note, conversation_context, user_facts, status, tenant_id) "
        "VALUES (%s, %s, %s, %s::jsonb, %s, %s::uuid) "
        "RETURNING id",
        (user_id, note, "用戶: 門打不開\n客服: 請確認電池", '{"model": "test"}', status, tenant_id),
    )
    row = await cur.fetchone()
    return row[0]


async def _cleanup(correction_id: int) -> None:
    """DELETE by id（cleanup，避免污染其他 test）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM data_corrections WHERE id = %s",
        (correction_id,),
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
# List — tenant 過濾 + status filter
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_list_returns_own_tenant_corrections(client):
    """list 只回傳 DEFAULT_TENANT 的列，不回傳 OTHER_TENANT 的列。"""
    own_id = await _insert_correction(tenant_id=DEFAULT_TENANT_ID)
    other_id = await _insert_correction(tenant_id=OTHER_TENANT_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        ids = [item["id"] for item in body["items"]]
        assert own_id in ids
        assert other_id not in ids
    finally:
        await _cleanup(own_id)
        await _cleanup(other_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_status_filter(client):
    """status=pending 只回傳 pending 列；approved 的列不出現。"""
    pending_id = await _insert_correction(status="pending")
    approved_id = await _insert_correction(status="approved")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections?status=pending",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["id"] for item in body["items"]]
        assert pending_id in ids
        assert approved_id not in ids
    finally:
        await _cleanup(pending_id)
        await _cleanup(approved_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_resolved_status_filter(client):
    """status=resolved 回傳正確（HD-2 第四態）。"""
    resolved_id = await _insert_correction(status="resolved")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections?status=resolved",
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert resolved_id in ids
    finally:
        await _cleanup(resolved_id)


# ─────────────────────────────────────────────────────────────────────────────
# Get — 404
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_get_not_found(client):
    """不存在的 correctionId → 404。"""
    headers = _make_headers(ADMIN_USER_ID)
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/999999999",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_found(client):
    """存在的 correctionId → 200 + {data: correction}。"""
    cid = await _insert_correction()
    try:
        headers = _make_headers(ADMIN_USER_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert body["data"]["id"] == cid
    finally:
        await _cleanup(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Approve — pending→approved OK；非 pending→409
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_approve_pending_to_approved(client):
    """pending→approved 正常轉換；response 帶 reviewed_by。"""
    cid = await _insert_correction(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:approve",
            headers=headers,
            json={"review_note": "確認無誤"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "approved"
        assert body["data"]["reviewed_by"] == ADMIN_USER_ID
        assert body["data"]["review_note"] == "確認無誤"
    finally:
        await _cleanup(cid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_approve_non_pending_409(client):
    """非 pending 狀態（已 approved）再 approve → 409 CONFLICT。"""
    cid = await _insert_correction(status="approved")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:approve",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
    finally:
        await _cleanup(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Reject — pending→rejected OK
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_reject_pending_to_rejected(client):
    """pending→rejected 正常轉換。"""
    cid = await _insert_correction(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:reject",
            headers=headers,
            json={"review_note": "資料有誤"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "rejected"
    finally:
        await _cleanup(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Resolve — approved→resolved OK；非 approved→409
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_approved_to_resolved(client):
    """approved→resolved 正常轉換（HD-2 第四態）。"""
    cid = await _insert_correction(status="approved")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:resolve",
            headers=headers,
            json={"review_note": "已更新知識庫"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "resolved"
        assert body["data"]["review_note"] == "已更新知識庫"
    finally:
        await _cleanup(cid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_non_approved_409(client):
    """非 approved 狀態（pending）resolve → 409 CONFLICT。"""
    cid = await _insert_correction(status="pending")
    try:
        headers = _make_headers(ADMIN_USER_ID)
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:resolve",
            headers=headers,
            json={},
        )
        assert resp.status_code == 409
    finally:
        await _cleanup(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-tenant guard → 403
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_list_403(client):
    """用 DEFAULT_TENANT token 打 OTHER_TENANT 路徑 → 403。"""
    headers = _make_headers(ADMIN_USER_ID, tenant_id=DEFAULT_TENANT_ID)
    resp = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/data-corrections",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.component
@pytest.mark.asyncio
async def test_cross_tenant_get_404(client):
    """OTHER_TENANT 的列用 DEFAULT_TENANT token get → 404（tenant 過濾，非洩漏 403）。"""
    cid = await _insert_correction(tenant_id=OTHER_TENANT_ID)
    try:
        headers = _make_headers(ADMIN_USER_ID, tenant_id=DEFAULT_TENANT_ID)
        resp = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}",
            headers=headers,
        )
        # 因為 WHERE id=X AND tenant_id=DEFAULT_TENANT → not found → 404
        assert resp.status_code == 404
    finally:
        await _cleanup(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Require_admin — 非 admin 呼叫 approve → 403
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_approve_non_admin_403(client):
    """customer_service 角色呼叫 approve → 403（HD-4）。"""
    cid = await _insert_correction(status="pending")
    try:
        headers = _make_headers(CS_USER_ID, role="customer_service")
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:approve",
            headers=headers,
            json={},
        )
        assert resp.status_code == 403
    finally:
        await _cleanup(cid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_reject_non_admin_403(client):
    """非 admin 角色呼叫 reject → 403（HD-4）。"""
    cid = await _insert_correction(status="pending")
    try:
        headers = _make_headers(CS_USER_ID, role="customer_service")
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:reject",
            headers=headers,
            json={},
        )
        assert resp.status_code == 403
    finally:
        await _cleanup(cid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_non_admin_403(client):
    """非 admin 角色呼叫 resolve → 403（HD-4）。"""
    cid = await _insert_correction(status="approved")
    try:
        headers = _make_headers(CS_USER_ID, role="customer_service")
        headers["Idempotency-Key"] = _idem_key()
        resp = await client.post(
            f"/tenants/{DEFAULT_TENANT_ID}/data-corrections/{cid}:resolve",
            headers=headers,
            json={},
        )
        assert resp.status_code == 403
    finally:
        await _cleanup(cid)
