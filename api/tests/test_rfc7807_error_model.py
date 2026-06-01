"""RFC7807 problem+json error model — component tests.

驗證：
1. Content-Type 回 application/problem+json
2. body 同時含 RFC7807 欄位（type/title/status/detail）AND legacy 欄位（error_code/message）
3. status 欄位 == HTTP status（superset 零破壞護欄）

TDD：先寫 RED → 改 errors.py → GREEN。

標 @pytest.mark.component 但大部分 case 不需 live DB（只觸發 validation 或 auth 錯誤）。
需 live DB 的 case（test_missing_sod_headers_403）以 skip guard 保護。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_problem_json_shape(res, *, expected_status: int) -> dict:
    """Common assertions for RFC7807 superset response shape."""
    # 1. Content-Type
    ct = res.headers.get("content-type", "")
    assert "application/problem+json" in ct, (
        f"Expected application/problem+json, got: {ct!r}"
    )

    body = res.json()

    # 2. RFC7807 required fields
    assert "type" in body, f"Missing 'type' field: {body}"
    assert "title" in body, f"Missing 'title' field: {body}"
    assert "status" in body, f"Missing 'status' field: {body}"
    assert "detail" in body, f"Missing 'detail' field: {body}"

    # 3. Legacy backward-compat fields (superset guarantee)
    assert "error_code" in body, f"Missing legacy 'error_code' field: {body}"
    assert "message" in body, f"Missing legacy 'message' field: {body}"

    # 4. status field == HTTP status
    assert body["status"] == expected_status, (
        f"body.status={body['status']} != HTTP {expected_status}"
    )

    # 5. type URI format (urn:smartlock:error:{error_code_lowercase})
    assert body["type"].startswith("urn:smartlock:error:"), (
        f"type URI must start with 'urn:smartlock:error:': {body['type']!r}"
    )

    return body


# ---------------------------------------------------------------------------
# 422 Validation Error (no DB needed — Pydantic intercept)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validation_error_422_is_problem_json(client):
    """POST /api/v1/auth/login 送空 body → 422 VALIDATION_ERROR → problem+json.

    不需 live DB — Pydantic 攔截 schema 錯誤，不到 DB 層。
    """
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "short"},  # invalid email + short password → 422
    )
    assert res.status_code == 422
    body = _assert_problem_json_shape(res, expected_status=422)
    assert body["error_code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 401 — missing auth (no DB needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_auth_401_is_problem_json(client):
    """GET /api/v1/work-orders 無 token → 401 → problem+json."""
    res = await client.get("/api/v1/work-orders")
    assert res.status_code == 401
    body = _assert_problem_json_shape(res, expected_status=401)
    assert body["error_code"] == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# 403 — tenant mismatch (no live DB for user lookup, but token guard fires)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_mismatch_403_is_problem_json(client, admin_token):
    """X-Tenant-ID mismatch → 403 → problem+json（error_code 由 ApiError 決定）。"""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    }
    res = await client.get("/api/v1/work-orders", headers=headers)
    assert res.status_code == 403
    body = _assert_problem_json_shape(res, expected_status=403)
    # error_code is FORBIDDEN or more specific (e.g. TENANT_MISMATCH) — both valid
    assert "error_code" in body  # backward-compat guard: field must exist


# ---------------------------------------------------------------------------
# Backward-compat guard: error_code still readable on 422 (superset invariant)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_code_still_present_on_422(client):
    """Superset 零破壞護欄：error_code 仍存在，前端 legacy caller 不紅。"""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "short"},
    )
    assert res.status_code == 422
    body = res.json()
    # Both new RFC7807 and legacy fields present
    assert "error_code" in body  # legacy
    assert "type" in body         # RFC7807
    assert body["error_code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# instance field — should be request path or request_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_instance_field_present(client):
    """instance 欄位應存在（可為 path 或 request_id）。"""
    res = await client.get("/api/v1/work-orders")
    assert res.status_code == 401
    body = res.json()
    # instance is optional per RFC7807 §3.1 but we include it
    assert "instance" in body, f"Missing 'instance' field: {body}"
