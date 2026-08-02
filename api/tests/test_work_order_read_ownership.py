"""技師讀取單筆工單與子資源的擁有權守衛（2026-08-02）。

**這是前一次修正的補洞。** 2026-08-02 稍早補上工單**列表**的角色收斂後，
SC-13～19 探針實跑抓到收斂只做了一半——單筆與子資源全都只有 `Depends(require_tenant)`，
技師拿別人的工單 id 直接打就 200：

  - detail 與 admin 逐欄比對只差 customer_phone 與 address
  - quote-items 品項、對外價、總額全露
  - **document 回 200 application/pdf，位元組數與 admin 取得的完全一致**

對照組已排除「守衛整支沒掛」：換租戶 id 時 admin 與技師都 403 CROSS_TENANT_READ。
缺的是同租戶內的 per-work-order 擁有權檢查。

**修過頭的風險比漏修更難發現**：搶單池的單本來就要讓技師看得到才能決定接不接。
所以本檔的第一優先是釘住「池子的單仍然看得見」——沒有那條，這個守衛會靜默打壞搶單。

回 404 而非 403 是刻意的：技師沒有合法管道得知那張單存在（自己的列表與池子都濾掉了），
回 403 等於確認存在性、可被拿來枚舉租戶內的工單 id。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _seed(status: str, assign_to_tech: bool) -> tuple[str, str, str]:
    """建 (我的 user_id, 我的 technician_id, 工單 id)。

    assign_to_tech=False → 工單指派給**別的**技師（或不指派，看 status）。
    """
    assert await db_module._ensure_conn(), "需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    me_user, me_tech = str(uuid.uuid4()), str(uuid.uuid4())
    other_tech = str(uuid.uuid4())
    other_user = str(uuid.uuid4())
    wo_id, pc_id = str(uuid.uuid4()), str(uuid.uuid4())

    for uid, name in ((me_user, "owner"), (other_user, "other")):
        await conn.execute(
            "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, %s, 'x', 'technician', TRUE) ON CONFLICT (id) DO NOTHING",
            (uid, DEFAULT_TENANT_ID, f"{name}-{uid[:8]}@example.com"),
        )
    for tid, uid, nm in ((me_tech, me_user, "我"), (other_tech, other_user, "別人")):
        await conn.execute(
            "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
            (tid, DEFAULT_TENANT_ID, uid, nm, f"09{tid[:8]}"),
        )
    await conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, source, knowledge_ready, brand) "
        "VALUES (%s::uuid, %s::uuid, 'manual', FALSE, 'Chatlock') ON CONFLICT (id) DO NOTHING",
        (pc_id, DEFAULT_TENANT_ID),
    )
    if status == "created" and not assign_to_tech:
        tech_col = None            # 池子：未認領
    else:
        tech_col = me_tech if assign_to_tech else other_tech
    await conn.execute(
        "INSERT INTO work_orders (id, tenant_id, technician_id, problem_card_id, status, brand) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, 'Chatlock') ON CONFLICT (id) DO NOTHING",
        (wo_id, DEFAULT_TENANT_ID, tech_col, pc_id, status),
    )
    return me_user, me_tech, wo_id


def _tech_headers(user_id: str) -> dict[str, str]:
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=user_id, role="technician", tenant_id=DEFAULT_TENANT_ID, token_type="access"
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": DEFAULT_TENANT_ID}


def _paths(wo_id: str) -> list[str]:
    t = DEFAULT_TENANT_ID
    return [
        f"/tenants/{t}/work-orders/{wo_id}",
        f"/tenants/{t}/work-orders/{wo_id}/quote-items",
        f"/api/v1/work-orders/{wo_id}",
        f"/api/v1/work-orders/{wo_id}/events",
    ]


# ── 最優先：不可修過頭 ──────────────────────────────────────────────


async def test_pool_work_order_still_visible_to_technician(client):
    """搶單池的單（created 且未認領）技師**必須**看得到——否則搶單功能被打壞。

    這條排在最前面是刻意的：漏修會被探針抓到，修過頭卻會靜默壞掉搶單。
    """
    me_user, _me_tech, wo_id = await _seed("created", assign_to_tech=False)
    for path in _paths(wo_id):
        r = await client.get(path, headers=_tech_headers(me_user))
        assert r.status_code == 200, f"池子的單技師應看得到：{path} → {r.status_code}"


async def test_own_work_order_readable(client):
    """指派給自己的單當然要看得到。"""
    me_user, _me_tech, wo_id = await _seed("assigned", assign_to_tech=True)
    for path in _paths(wo_id):
        r = await client.get(path, headers=_tech_headers(me_user))
        assert r.status_code == 200, f"自己的單應可讀：{path} → {r.status_code}"


# ── 破口本身 ───────────────────────────────────────────────────────


async def test_other_technicians_work_order_is_hidden(client, admin_headers):
    """別人的單：技師一律 404；admin 對照組 200（證明端點正常、404 不是端點壞了）。"""
    me_user, _me_tech, wo_id = await _seed("assigned", assign_to_tech=False)
    for path in _paths(wo_id):
        r_admin = await client.get(path, headers=admin_headers)
        assert r_admin.status_code == 200, f"對照組 admin 應可讀：{path} → {r_admin.status_code}"
        r_tech = await client.get(path, headers=_tech_headers(me_user))
        assert r_tech.status_code == 404, f"別人的單技師不得讀到：{path} → {r_tech.status_code}"


async def test_document_pdf_of_other_technician_is_hidden(client):
    """PDF 下載是最嚴重的一條——修正前位元組數與 admin 取得的完全一致。"""
    me_user, _me_tech, wo_id = await _seed("assigned", assign_to_tech=False)
    r = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{wo_id}/document",
        headers=_tech_headers(me_user),
    )
    assert r.status_code == 404, f"不得下載別人工單的 PDF（實得 {r.status_code}）"


async def test_evidence_package_of_other_technician_is_hidden(client):
    me_user, _me_tech, wo_id = await _seed("assigned", assign_to_tech=False)
    r = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{wo_id}/evidence-package",
        headers=_tech_headers(me_user),
    )
    assert r.status_code == 404


async def test_404_not_403_avoids_existence_leak(client):
    """不存在的 id 與「存在但不是我的」必須無法區分，否則可枚舉租戶內工單 id。"""
    me_user, _me_tech, real_wo = await _seed("assigned", assign_to_tech=False)
    fake_wo = str(uuid.uuid4())
    path = f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{{}}"
    r_real = await client.get(path.format(real_wo), headers=_tech_headers(me_user))
    r_fake = await client.get(path.format(fake_wo), headers=_tech_headers(me_user))
    assert r_real.status_code == r_fake.status_code == 404, "兩者必須同樣回應"


# ── 不得誤傷其他角色 ────────────────────────────────────────────────


async def test_non_technician_roles_unaffected(client, admin_headers, dispatcher_headers):
    """守衛只對 technician 生效；admin／dispatcher 行為完全不變。"""
    _me_user, _me_tech, wo_id = await _seed("assigned", assign_to_tech=False)
    path = f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{wo_id}"
    assert (await client.get(path, headers=admin_headers)).status_code == 200
    assert (await client.get(path, headers=dispatcher_headers)).status_code == 200
