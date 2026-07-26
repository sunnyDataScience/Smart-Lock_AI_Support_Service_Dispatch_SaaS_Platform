"""CR-0182（UAT-0723-F2）：跨面 token 守衛（portal claim + ALLOWED_TOKEN_PORTALS）。

F2＝技師 token（role=technician）打 brand-api 讀客戶 PII/退款金流。守衛：本服務只接受
ALLOWED_TOKEN_PORTALS 列出的面向 token；缺 portal 由 role 即時推導（涵蓋 SSO / 部署後
1h 舊 token）；未設 env=不強制（本機/pytest 之 API_SURFACE=all 沿用既有行為）。
"""

from __future__ import annotations

import pytest

from core.auth import create_token, decode_token, portal_for_role

pytestmark = pytest.mark.unit

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ── 純函式：role → portal 推導 ────────────────────────────────────────────────
def test_technician_maps_to_tech():
    assert portal_for_role("technician") == "tech"


def test_platform_roles_map_to_platform():
    assert portal_for_role("platform_admin") == "platform"
    assert portal_for_role("platform_keeper") == "platform"


def test_brand_roles_map_to_brand():
    for r in ("admin", "operations_manager", "dispatcher", "customer_service",
              "reviewer", "viewer", "vendor"):
        assert portal_for_role(r) == "brand", r


def test_empty_or_none_role_denied():
    # 空/缺 role = 異常 token → None（呼叫端 deny，不落最敏感的 brand）
    assert portal_for_role("") is None
    assert portal_for_role(None) is None


def test_unknown_nonempty_role_defaults_brand():
    # 未列但非空 role → brand（可用性安全；per-endpoint role_required 仍會擋）
    assert portal_for_role("some_future_role") == "brand"


# ── 簽發：portal 寫進 payload 且不破 decode（不用標準 aud，避 jose 驗證）──────────
def test_token_carries_portal_claim_and_decodes():
    tok, _, _ = create_token(
        user_id="u", role="technician", tenant_id=DEFAULT_TENANT_ID, token_type="access")
    payload = decode_token(tok)  # 不帶 audience 參數也不炸（證明非標準 aud 欄）
    assert payload["portal"] == "tech"
    assert payload["role"] == "technician"


def test_brand_token_portal_is_brand():
    tok, _, _ = create_token(
        user_id="u", role="admin", tenant_id=DEFAULT_TENANT_ID, token_type="access")
    assert decode_token(tok)["portal"] == "brand"


# ── env 驅動的允許集 ──────────────────────────────────────────────────────────
def test_allowed_portals_unset_is_no_enforcement(monkeypatch):
    from core import deps
    monkeypatch.delenv("ALLOWED_TOKEN_PORTALS", raising=False)
    assert deps._allowed_portals() is None


def test_allowed_portals_parsed(monkeypatch):
    from core import deps
    monkeypatch.setenv("ALLOWED_TOKEN_PORTALS", "brand")
    assert deps._allowed_portals() == frozenset({"brand"})
    monkeypatch.setenv("ALLOWED_TOKEN_PORTALS", "brand, tech")
    assert deps._allowed_portals() == frozenset({"brand", "tech"})


# ── 元件：跨面請求被擋（403 短路於 DB 查詢前，不需 DB）──────────────────────────
@pytest.mark.component
@pytest.mark.asyncio
async def test_tech_token_denied_on_brand_service(client, monkeypatch):
    """ALLOWED_TOKEN_PORTALS=brand 時，技師 token 打 brand 客戶端點 → 403 CROSS_PORTAL_FORBIDDEN。"""
    monkeypatch.setenv("ALLOWED_TOKEN_PORTALS", "brand")
    tech_tok, _, _ = create_token(
        user_id="33333333-3333-3333-3333-333333333333",
        role="technician", tenant_id=DEFAULT_TENANT_ID, token_type="access")
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers?limit=1",
        headers={"Authorization": f"Bearer {tech_tok}", "X-Tenant-ID": DEFAULT_TENANT_ID},
    )
    assert resp.status_code == 403
    assert resp.json().get("error_code") == "CROSS_PORTAL_FORBIDDEN"


@pytest.mark.component
@pytest.mark.asyncio
async def test_brand_token_passes_gate(client, monkeypatch):
    """ALLOWED_TOKEN_PORTALS=brand 時，admin token 通過守衛（不得回 CROSS_PORTAL_FORBIDDEN）。"""
    monkeypatch.setenv("ALLOWED_TOKEN_PORTALS", "brand")
    admin_tok, _, _ = create_token(
        user_id="c782bcfe-89bb-40b3-94b3-8c73d7bd0961",
        role="admin", tenant_id=DEFAULT_TENANT_ID, token_type="access")
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers?limit=1",
        headers={"Authorization": f"Bearer {admin_tok}", "X-Tenant-ID": DEFAULT_TENANT_ID},
    )
    assert resp.json().get("error_code") != "CROSS_PORTAL_FORBIDDEN"


@pytest.mark.component
@pytest.mark.asyncio
async def test_no_enforcement_when_env_unset(client, monkeypatch):
    """env 未設 → 守衛不強制：技師 token 不因 portal 被擋（回歸，保 local/pytest 行為）。"""
    monkeypatch.delenv("ALLOWED_TOKEN_PORTALS", raising=False)
    tech_tok, _, _ = create_token(
        user_id="33333333-3333-3333-3333-333333333333",
        role="technician", tenant_id=DEFAULT_TENANT_ID, token_type="access")
    resp = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/customers?limit=1",
        headers={"Authorization": f"Bearer {tech_tok}", "X-Tenant-ID": DEFAULT_TENANT_ID},
    )
    assert resp.json().get("error_code") != "CROSS_PORTAL_FORBIDDEN"
