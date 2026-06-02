"""Component + unit tests for POST /tenants/{tenantId}/technicians — createTechnician（P2-W1）。

測試矩陣：
  Unit（pure, no I/O）:
    U-1  request schema validation — required fields missing → ValidationError
    U-2  request schema validation — valid payload → model parses OK

  Component（pytest.mark.component — 需 DB seed）：
    C-1  POST /tenants/{tenantId}/technicians → 201 + Idempotency-Key（fresh uuid）
    C-2  同 Idempotency-Key 重送 → 200 replay（idempotency dedup）
    C-3  cross-tenant POST → 403 CROSS_TENANT_WRITE
    C-4  缺 required field display_name → 422 Unprocessable Entity
    C-5  缺 required field coverage_areas → 422 Unprocessable Entity

注意：component 測試須在有 DB 的環境跑；unit 測試無 I/O，可在任意環境執行。
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

# 確保 api/ 在 sys.path 內（conftest.py 也會補，但 unit marker 不依賴 conftest）
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Shared payload factory
# ---------------------------------------------------------------------------


def _onboard_payload(
    display_name: str = "測試技師-P2W1",
    coverage_areas: list[str] | None = None,
) -> dict:
    return {
        "display_name": display_name,
        "coverage_areas": coverage_areas if coverage_areas is not None else ["taipei", "new_taipei"],
    }


# ---------------------------------------------------------------------------
# Unit tests — pure schema validation (pytest.mark.unit, no I/O)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_technician_create_request_missing_display_name():
    """U-1a: display_name 缺失 → ValidationError。"""
    from pydantic import ValidationError
    from routers.technicians_v2 import _TechnicianCreateRequest

    with pytest.raises(ValidationError):
        _TechnicianCreateRequest(coverage_areas=["taipei"])


@pytest.mark.unit
def test_technician_create_request_missing_coverage_areas():
    """U-1b: coverage_areas 缺失 → ValidationError。"""
    from pydantic import ValidationError
    from routers.technicians_v2 import _TechnicianCreateRequest

    with pytest.raises(ValidationError):
        _TechnicianCreateRequest(display_name="技師甲")


@pytest.mark.unit
def test_technician_create_request_valid():
    """U-2: 完整合法 payload → model 解析成功，optional 欄位為 None。"""
    from routers.technicians_v2 import _TechnicianCreateRequest

    req = _TechnicianCreateRequest(
        display_name="技師乙",
        coverage_areas=["taipei", "new_taipei"],
    )
    assert req.display_name == "技師乙"
    assert req.coverage_areas == ["taipei", "new_taipei"]
    assert req.phone is None
    assert req.email is None
    assert req.capabilities is None


@pytest.mark.unit
def test_technician_create_request_optional_fields():
    """U-3: optional 欄位（phone/email/capabilities）可正常傳入。"""
    from routers.technicians_v2 import _TechnicianCreateRequest

    req = _TechnicianCreateRequest(
        display_name="技師丙",
        coverage_areas=["taichung"],
        phone="0912345678",
        email="tech@example.com",
        capabilities=["Dormakaba", "Philips"],
    )
    assert req.phone == "0912345678"
    assert req.email == "tech@example.com"
    assert req.capabilities == ["Dormakaba", "Philips"]


# ---------------------------------------------------------------------------
# Component tests — API layer (pytest.mark.component, needs DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_technician_v2_201(client, admin_headers):
    """C-1: POST /tenants/{tenantId}/technicians → 201 + envelope {data}。
    使用 fresh Idempotency-Key（uuid4）確保每次跑都是新建。
    """
    idempotency_key = str(uuid.uuid4())
    # 使用唯一 display_name 避免業務唯一鍵衝突影響其他測試
    unique_name = f"onboard-test-{idempotency_key[:8]}"

    headers = {**admin_headers, "Idempotency-Key": idempotency_key}
    payload = _onboard_payload(display_name=unique_name)

    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert "data" in body
    data = body["data"]
    assert "id" in data
    assert data["name"] == unique_name


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_technician_v2_idempotency_replay(client, admin_headers):
    """C-2: 同一 Idempotency-Key 重送 → 200（replay / 業務唯一鍵命中），回相同 id。"""
    idempotency_key = str(uuid.uuid4())
    unique_name = f"idem-test-{idempotency_key[:8]}"
    headers = {**admin_headers, "Idempotency-Key": idempotency_key}
    payload = _onboard_payload(display_name=unique_name)

    # 第一次建立
    res1 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json=payload,
        headers=headers,
    )
    assert res1.status_code == 201, res1.text
    first_id = res1.json()["data"]["id"]

    # 第二次相同 key → 業務唯一鍵命中回 200，或 idempotency dedup 回 201
    # 兩種情境都合法：重點是回傳的 data.id 相同
    res2 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json=payload,
        headers=headers,
    )
    assert res2.status_code in (200, 201), res2.text
    assert res2.json()["data"]["id"] == first_id


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_technician_v2_cross_tenant_403(client):
    """C-3: JWT tenant 與 path tenantId 不符 → 403 CROSS_TENANT_WRITE。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role="admin",
        tenant_id=DEFAULT_TENANT_ID,
        token_type="access",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
        "Idempotency-Key": str(uuid.uuid4()),
    }
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/technicians",
        json=_onboard_payload(),
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_technician_v2_missing_display_name_422(client, admin_headers):
    """C-4: display_name 缺失 → 422 Unprocessable Entity。"""
    headers = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"coverage_areas": ["taipei"]},
        headers=headers,
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_technician_v2_missing_coverage_areas_422(client, admin_headers):
    """C-5: coverage_areas 缺失 → 422 Unprocessable Entity。"""
    headers = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        json={"display_name": "缺欄位技師"},
        headers=headers,
    )
    assert res.status_code == 422, res.text
