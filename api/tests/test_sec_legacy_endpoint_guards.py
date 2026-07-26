"""CR-0183 補漏（2026-07-27）：legacy `/api/v1` 孿生端點與明細/stats 的角色守衛。

**發現**：CR-0183 為 v2 tenant-scoped 端點補了角色守衛，但同義的 legacy `/api/v1`
端點（兩者皆掛載於 main.py）與 v2 自己的 stats／明細端點漏掛 → 低權限角色只要改打
legacy 路徑或明細路徑即可**完全繞過** v2 的守衛，讀到金流（refunds）與 PII（customers）。

驗收：同一個低權限角色打「v2 路徑」與「legacy／明細路徑」必須得到**一致**的 403，
不得有任一條路徑放行（防止「新路徑上鎖、舊路徑沒鎖」這類繞道復發）。
"""

from __future__ import annotations

import pytest

from core.auth import create_token

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


def _hdr(role: str) -> dict:
    t, _, _ = create_token(user_id="00000000-0000-0000-0000-0000000000aa",
                           role=role, tenant_id=TID, token_type="access")
    return {"Authorization": f"Bearer {t}", "X-Tenant-ID": TID}


# 每組＝同一資源的所有等價路徑（v2 + legacy + 明細/stats），必須守衛一致。
# (組名, [路徑…], 應被擋角色, 應通過角色)
EQUIVALENT_PATHS = [
    (
        "refunds（金流 REVIEW_ROLES）",
        [
            f"/tenants/{TID}/refunds?limit=1",   # v2：CR-0183 已守
            "/api/v1/refunds?limit=1",           # legacy：本次補（原可繞道）
        ],
        "customer_service",
        "reviewer",
    ),
    (
        "customers（PII admin/ops/cs）",
        [
            f"/tenants/{TID}/customers?limit=1",        # v2 list：CR-0183 已守
            f"/tenants/{TID}/customers/stats",          # v2 stats：本次補
            "/api/v1/customers?limit=1",                # legacy list：本次補
        ],
        "reviewer",
        "customer_service",
    ),
    (
        "warranty-claims（REVIEW_ROLES）",
        [
            f"/tenants/{TID}/warranty-claims?limit=1",  # v2：已守
            "/api/v1/warranty-claims?limit=1",          # legacy：本次補
        ],
        "customer_service",
        "reviewer",
    ),
    (
        "reconciliations（REVIEW_ROLES）",
        [
            f"/tenants/{TID}/accounting/reconciliations?limit=1",
            "/api/v1/accounting/reconciliations?limit=1",   # legacy：本次補
        ],
        "customer_service",
        "operations_manager",
    ),
    (
        "pricing/rules（OPS_ROLES）",
        [
            f"/tenants/{TID}/pricing/rules?limit=1",
            "/api/v1/pricing/rules?limit=1",                # legacy：本次補
        ],
        "customer_service",
        "operations_manager",
    ),
    (
        "sentiment/alerts（BACKOFFICE_ROLES）",
        [
            f"/tenants/{TID}/sentiment/alerts?limit=1",
            "/api/v1/sentiment/alerts?limit=1",             # legacy：本次補
        ],
        "technician",
        "customer_service",
    ),
    (
        "conversations（BACKOFFICE+reviewer）",
        [
            f"/tenants/{TID}/conversations?limit=1",
            "/api/v1/conversations?limit=1",                # legacy：本次補
        ],
        "technician",
        "customer_service",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("label,paths,blocked_role,allowed_role", EQUIVALENT_PATHS,
                         ids=[c[0] for c in EQUIVALENT_PATHS])
async def test_no_bypass_via_equivalent_path(client, label, paths, blocked_role, allowed_role):
    """低權限角色在**每一條**等價路徑都必須被擋——任一條放行＝繞道漏洞。"""
    for path in paths:
        resp = await client.get(path, headers=_hdr(blocked_role))
        assert resp.status_code == 403, (
            f"[{label}] {path} 未擋 {blocked_role}（得 {resp.status_code}）＝存在繞道路徑"
        )
        assert resp.json().get("error_code") == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("label,paths,blocked_role,allowed_role", EQUIVALENT_PATHS,
                         ids=[c[0] for c in EQUIVALENT_PATHS])
async def test_legit_role_not_broken_on_any_path(client, label, paths, blocked_role, allowed_role):
    """合法角色在每條路徑都不得被誤擋（防補守衛時修過頭擋掉正常使用者）。"""
    for path in paths:
        resp = await client.get(path, headers=_hdr(allowed_role))
        assert resp.json().get("error_code") != "FORBIDDEN", \
            f"[{label}] {path} 誤擋合法角色 {allowed_role}"


@pytest.mark.asyncio
async def test_customer_detail_guard_not_weaker_than_list(client):
    """明細端點守衛不得弱於 list（明細含 PII 聚合：工單/評分/投訴/退款）。"""
    cid = "00000000-0000-0000-0000-0000000000c1"
    for path in (f"/tenants/{TID}/customers/{cid}", f"/api/v1/customers/{cid}"):
        resp = await client.get(path, headers=_hdr("reviewer"))
        assert resp.status_code == 403, f"{path} 明細守衛弱於 list（reviewer 應被擋）"


@pytest.mark.asyncio
async def test_refund_detail_guard_consistent(client):
    """退款明細 legacy 路徑守衛與 v2 一致。"""
    rid = "00000000-0000-0000-0000-0000000000r1".replace("r", "a")
    for path in (f"/tenants/{TID}/refunds/{rid}", f"/api/v1/refunds/{rid}"):
        resp = await client.get(path, headers=_hdr("customer_service"))
        assert resp.status_code == 403, f"{path} 未擋 customer_service"
