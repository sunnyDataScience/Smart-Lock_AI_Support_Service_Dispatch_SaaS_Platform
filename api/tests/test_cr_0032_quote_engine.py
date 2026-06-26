"""CR-0032 報價引擎 Phase A 測試（component，真 DB；依賴 migration 040 catalog + 041 quote）。

- create_quote → draft + 有效期
- add_line(service_code) → 從 catalog 帶價、recompute total
- 狀態機 submit→approve→send（凍結 snapshot hash）→accept
- include_cost RBAC 遮蔽 unit_price
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID


pytestmark = pytest.mark.component


async def _seed_wo() -> tuple[str, list]:
    uid = str(uuid.uuid4()); cid = str(uuid.uuid4()); pcid = str(uuid.uuid4()); woid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')", (uid, DEFAULT_TENANT_ID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)", (cid, uid, f"s-{uid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status) VALUES (%s::uuid, %s::uuid, 'confirmed')", (pcid, cid))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_address) "
        "VALUES (%s::uuid, %s::uuid, 'created', '新北市板橋區文化路1號')", (woid, pcid))
    return woid, [woid, pcid, cid, uid]


async def _cleanup(ids: list, quote_id: str | None = None) -> None:
    if quote_id:
        await db_module._conn.execute("DELETE FROM quote WHERE id = %s::uuid", (quote_id,))  # cascade lines/approval/snapshot
    woid, pcid, cid, uid = ids
    # CR-0035：accept 會 best-effort 開發票（invoices FK work_orders ON DELETE RESTRICT），先刪
    await db_module._conn.execute("DELETE FROM invoices WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pcid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_create_add_line_from_catalog_and_total(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        assert q["state"] == "draft" and q["expiry_at"]
        # SVC-RES-001 到府檢測 建議客戶價 800（catalog mock）
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001", quantity=1)
        assert q["total_amount"] == "800.00"
        assert q["lines"][0]["service_code"] == "SVC-RES-001"
        # 加材料 MAT-PWR-001 售價 300 ×2 = 600 → total 1400
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], material_code="MAT-PWR-001", quantity=2)
        assert q["total_amount"] == "1400.00"
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_remove_line_recompute_total(client):
    """移除報價明細（add_line 反向）→ 重算總額；移除不存在明細 → 404。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001", quantity=1)  # 800
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], material_code="MAT-PWR-001", quantity=2)  # +600=1400
        assert len(q["lines"]) == 2 and q["total_amount"] == "1400.00"
        # 移除服務項（800）→ 重算 600、剩 1 項
        svc_line = next(l for l in q["lines"] if l.get("service_code") == "SVC-RES-001")
        q = await qe.remove_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], line_id=svc_line["id"])
        assert len(q["lines"]) == 1
        assert q["total_amount"] == "600.00"
        # 移除不存在的明細 → 404
        with pytest.raises(ApiError) as ei:
            await qe.remove_line(
                tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], line_id=str(uuid.uuid4())
            )
        assert ei.value.status_code == 404
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_state_machine_and_snapshot_freeze(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-ELK-001")
        qid = q["id"]
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="submit")
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="approve", actor_id=ADMIN_USER_ID)
        sent = await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="send", actor_id=ADMIN_USER_ID)
        assert sent["state"] == "sent"
        assert sent["snapshot_hash"]  # 送客戶凍結了 snapshot
        accepted = await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="accept")
        assert accepted["state"] == "accepted"
        # 已 accepted 不能再 submit
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="submit")
        assert ei.value.status_code == 409
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_approval_threshold_blocks_draft_send(client):
    """總額超 _APPROVAL_THRESHOLD 不可從 draft 直送，須先 submit→approve（esales Q-11 mock 門檻）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        qid = q["id"]
        # SVC-RES-001 售價 800 × 20 = 16000 > 10000 門檻
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, service_code="SVC-RES-001", quantity=20)
        assert float(q["total_amount"]) > qe._APPROVAL_THRESHOLD
        # draft 直送 → 擋
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="send", actor_id=ADMIN_USER_ID)
        assert ei.value.status_code == 409 and ei.value.error_code == "APPROVAL_REQUIRED"
        # 走 submit→approve→send 則放行
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="submit")
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="approve", actor_id=ADMIN_USER_ID)
        sent = await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="send", actor_id=ADMIN_USER_ID)
        assert sent["state"] == "sent"
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_under_threshold_draft_send_ok(client):
    """總額在門檻內 → draft 可直送（免核）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        qid = q["id"]
        q = await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, service_code="SVC-RES-001", quantity=1)
        assert float(q["total_amount"]) <= qe._APPROVAL_THRESHOLD
        sent = await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="send", actor_id=ADMIN_USER_ID)
        assert sent["state"] == "sent"
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_send_mints_public_view_token(client):
    """送客戶 → 回傳客戶端查看連結（真 public_token，purpose=quote_view，CR-0032 Phase C）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001")
        sent = await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="send", actor_id=ADMIN_USER_ID)
        assert sent["state"] == "sent"
        assert sent["public_token"] and sent["public_path"].startswith("/quotes/")
        # 真 token 可被 verify_token 驗（allowlist 已含 quote_view），且綁回此報價
        from services import public_token
        payload = public_token.verify_token(sent["public_token"])
        assert payload.purpose == "quote_view"
        assert payload.subject_id == q["id"]
        assert payload.tenant_id == DEFAULT_TENANT_ID
        # 已送報價可重新取連結（後台複製用）
        relink = await qe.mint_view_token(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        assert relink["public_token"]
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_get_quote_cost_rbac(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid)
        await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001")
        admin = await qe.get_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], include_cost=True)
        cust = await qe.get_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], include_cost=False)
        assert "unit_price" in admin["lines"][0]
        assert "unit_price" not in cust["lines"][0]
        assert "customer_price" in cust["lines"][0]
    finally:
        await _cleanup(ids)
