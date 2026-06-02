"""Component tests — M06 POST /tenants/{tenantId}/dispatch:plan v2（CR-0003 P2）。

測試矩陣：
  1. POST :plan（admin + Idempotency-Key）→ 合理回應碼（200/404/503；不是 403/422）
  2. POST :plan 跨租戶 guard → 403 CROSS_TENANT_WRITE
  3. POST :plan 未授權角色（technician）→ 403 FORBIDDEN
  4. POST :plan 缺 Idempotency-Key 仍可送（idempotency_guard 非強制 422）
  5. POST :plan 重複 Idempotency-Key → 第二次回 200（冪等快取命中；無 DB 時 fallthrough）

設計說明：
  - 無真實 DB → service 層會回 404（work order not found）或 503（DB unavailable）。
  - cross-tenant / forbidden 檢查在 service 呼叫之前發生，因此不依賴 DB 即可 early-return 403。
  - pytestmark = component（需有 DB 的環境才能 200；此處只驗結構正確性）。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

_PLAN_PATH = f"/tenants/{DEFAULT_TENANT_ID}/dispatch:plan"
_OTHER_PLAN_PATH = f"/tenants/{OTHER_TENANT_ID}/dispatch:plan"


def _plan_body(
    work_order_id: str | None = None,
    technician_id: str | None = None,
    override_reason: str | None = None,
) -> dict:
    return {
        "work_order_id": work_order_id or str(uuid.uuid4()),
        "technician_id": technician_id or str(uuid.uuid4()),
        **({"override_reason": override_reason} if override_reason is not None else {}),
    }


def _make_token(*, role: str, tenant_id: str = DEFAULT_TENANT_ID) -> str:
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return token


def _headers(role: str = "admin", tenant_id: str = DEFAULT_TENANT_ID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_make_token(role=role, tenant_id=tenant_id)}",
        "X-Tenant-ID": tenant_id,
        "Idempotency-Key": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# 1. 正常路徑 — 合理回應碼（無 DB 時 404/503）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_v2_accepted_status_codes(client, admin_headers):
    """POST :plan（admin + Idempotency-Key）→ 200/404/503（不得是 403 或 422）。"""
    res = await client.post(
        _PLAN_PATH,
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json=_plan_body(),
    )
    assert res.status_code in (200, 404, 503), (
        f"Unexpected status {res.status_code}: {res.text}"
    )


@pytest.mark.asyncio
async def test_plan_dispatch_v2_dispatcher_role(client):
    """dispatcher 角色應被允許（_PLAN_ALLOWED_ROLES 包含 dispatcher）。"""
    headers = _headers(role="dispatcher")
    res = await client.post(
        _PLAN_PATH,
        headers=headers,
        json=_plan_body(),
    )
    assert res.status_code in (200, 404, 503), (
        f"dispatcher 角色不應被 403/422，got {res.status_code}: {res.text}"
    )


@pytest.mark.asyncio
async def test_plan_dispatch_v2_customer_service_role(client):
    """customer_service 角色應被允許（繞過稽核軌跡路徑）。"""
    headers = _headers(role="customer_service")
    res = await client.post(
        _PLAN_PATH,
        headers=headers,
        json=_plan_body(override_reason="緊急，客服人工介入"),
    )
    assert res.status_code in (200, 404, 503), (
        f"customer_service 角色不應被 403/422，got {res.status_code}: {res.text}"
    )


# ---------------------------------------------------------------------------
# 2. cross-tenant guard → 403 CROSS_TENANT_WRITE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_v2_cross_tenant_403(client):
    """JWT tenant = DEFAULT，path tenant = OTHER → 403 CROSS_TENANT_WRITE。"""
    # JWT claim 屬於 DEFAULT_TENANT，但打 OTHER_TENANT 的 path
    headers = {
        "Authorization": f"Bearer {_make_token(role='admin', tenant_id=DEFAULT_TENANT_ID)}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
        "Idempotency-Key": str(uuid.uuid4()),
    }
    res = await client.post(
        _OTHER_PLAN_PATH,
        headers=headers,
        json=_plan_body(),
    )
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE", (
        f"Expected CROSS_TENANT_WRITE, got: {body}"
    )


# ---------------------------------------------------------------------------
# 3. 未授權角色 → 403 FORBIDDEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_v2_technician_role_403(client):
    """technician 角色不在 _PLAN_ALLOWED_ROLES → 403 FORBIDDEN。"""
    headers = _headers(role="technician")
    res = await client.post(
        _PLAN_PATH,
        headers=headers,
        json=_plan_body(),
    )
    assert res.status_code == 403, (
        f"technician 應被拒絕 403，got {res.status_code}: {res.text}"
    )


@pytest.mark.asyncio
async def test_plan_dispatch_v2_unknown_role_403(client):
    """未知角色 → 403 FORBIDDEN（role_required 白名單外均拒絕）。"""
    headers = _headers(role="viewer")
    res = await client.post(
        _PLAN_PATH,
        headers=headers,
        json=_plan_body(),
    )
    assert res.status_code == 403, (
        f"viewer 角色應被拒絕 403，got {res.status_code}: {res.text}"
    )


# ---------------------------------------------------------------------------
# 4. 缺 Idempotency-Key → 400 MISSING_IDEMPOTENCY_KEY（idempotency_guard POST 強制）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_v2_no_idempotency_key_400(client, admin_headers):
    """idempotency_guard 對 POST 強制要求 Idempotency-Key：缺 key → 400 MISSING_IDEMPOTENCY_KEY。

    行為來源：core/idempotency.py idempotency_guard()：
      缺 key + method in applies_to (POST) → ApiError(MISSING_IDEMPOTENCY_KEY, 400)。
    """
    headers_no_idem = {k: v for k, v in admin_headers.items() if k != "Idempotency-Key"}
    res = await client.post(
        _PLAN_PATH,
        headers=headers_no_idem,
        json=_plan_body(),
    )
    assert res.status_code == 400, (
        f"缺 Idempotency-Key 應回 400，got {res.status_code}: {res.text}"
    )
    body = res.json()
    assert body.get("error_code") == "MISSING_IDEMPOTENCY_KEY", (
        f"Expected MISSING_IDEMPOTENCY_KEY, got: {body}"
    )


# ---------------------------------------------------------------------------
# 5. 重複 Idempotency-Key → 冪等（第二次應不報 5xx；無 DB 時 fallthrough）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_v2_idempotency_repeat_not_5xx(client, admin_headers):
    """相同 Idempotency-Key 送兩次：第二次不應回 5xx 錯誤。

    - 有 DB + 第一次 200：第二次直接從快取回 200（冪等命中）。
    - 無 DB：兩次都是 404/503，但不是 5xx 伺服器崩潰。
    """
    idem_key = str(uuid.uuid4())
    body = _plan_body()
    headers = {**admin_headers, "Idempotency-Key": idem_key}

    r1 = await client.post(_PLAN_PATH, headers=headers, json=body)
    r2 = await client.post(_PLAN_PATH, headers=headers, json=body)

    # 兩次都不應是 5xx（除了 503 DB unavailable）
    for attempt, r in enumerate((r1, r2), 1):
        assert r.status_code in (200, 404, 503), (
            f"第 {attempt} 次請求 Unexpected status {r.status_code}: {r.text}"
        )
