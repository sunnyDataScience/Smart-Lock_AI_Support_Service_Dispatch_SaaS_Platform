"""CR-0072 / TI-NOTIF-03 — 通知模板主管核准 gate（BR-M16-03）。

核准 gate：create→pending_approval；approve（主管+四眼）→approved；send 僅 approved 可發。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import notification_template_service as nts

TID = "00000000-0000-0000-0000-000000000001"
_SEED_USER = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"
CREATOR = str(uuid.uuid4())
APPROVER = str(uuid.uuid4())


# ── unit：非法 type / approver role gate（純邏輯）──
@pytest.mark.unit
def test_approver_roles_defined():
    from services.notification_template_service import APPROVER_ROLES, _visible_audiences
    assert "admin" in APPROVER_ROLES and "operations_manager" in APPROVER_ROLES
    assert "technician" not in APPROVER_ROLES
    assert _visible_audiences("admin") is None                      # 全可見
    assert "internal" not in (_visible_audiences("customer_service") or set())


async def _mk_template(audience="customer", created_by=CREATOR) -> str:
    t = await nts.create_template(
        tenant_id=TID, template_type="quote", title="測試報價",
        body_template="您的報價 {amount}", created_by=created_by, audience_role=audience)
    return t["id"]


async def _cleanup(tids):
    for t in tids:
        await db_module._conn.execute("DELETE FROM notifications WHERE template_id=%s::uuid", (t,))
        await db_module._conn.execute("DELETE FROM notification_template WHERE id=%s::uuid", (t,))


# ── create 預設 pending_approval ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_create_defaults_pending_approval():
    assert await db_module._ensure_conn()
    tid = await _mk_template()
    try:
        cur = await db_module._conn.execute(
            "SELECT status, approved_by FROM notification_template WHERE id=%s::uuid", (tid,))
        row = await cur.fetchone()
        assert row[0] == "pending_approval" and row[1] is None
    finally:
        await _cleanup([tid])
    # 非法 type → 422
    with pytest.raises(ApiError) as e:
        await nts.create_template(tenant_id=TID, template_type="nonsense", title="x",
                                  body_template="y", created_by=CREATOR)
    assert e.value.status_code == 422


# ── 未核准不可發 → 409 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_unapproved_template_cannot_send():
    assert await db_module._ensure_conn()
    tid = await _mk_template()
    try:
        with pytest.raises(ApiError) as e:
            await nts.send_from_template(tenant_id=TID, template_id=tid, target_user_id=_SEED_USER)
        assert e.value.error_code == "TEMPLATE_NOT_APPROVED" and e.value.status_code == 409
    finally:
        await _cleanup([tid])


# ── approve 後可發 + template_id 連回 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_approved_template_sends_and_links():
    assert await db_module._ensure_conn()
    tid = await _mk_template()
    try:
        await nts.approve_template(template_id=tid, approver_id=APPROVER, approver_role="admin")
        out = await nts.send_from_template(
            tenant_id=TID, template_id=tid, target_user_id=_SEED_USER, context={"amount": "NT$1500"})
        assert out["template_id"] == tid and out["type"] == "quote"
    finally:
        await _cleanup([tid])


# ── 四眼：建立者自核准 → 403 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_creator_cannot_self_approve():
    assert await db_module._ensure_conn()
    tid = await _mk_template(created_by=CREATOR)
    try:
        with pytest.raises(ApiError) as e:
            await nts.approve_template(template_id=tid, approver_id=CREATOR, approver_role="admin")
        assert e.value.status_code == 403
    finally:
        await _cleanup([tid])


# ── 非主管核准 → 403 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_non_supervisor_approve_forbidden():
    assert await db_module._ensure_conn()
    tid = await _mk_template()
    try:
        with pytest.raises(ApiError) as e:
            await nts.approve_template(template_id=tid, approver_id=APPROVER, approver_role="technician")
        assert e.value.error_code == "FORBIDDEN" and e.value.status_code == 403
    finally:
        await _cleanup([tid])


# ── 重複核准 → 409 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_double_approve_blocked():
    assert await db_module._ensure_conn()
    tid = await _mk_template()
    try:
        await nts.approve_template(template_id=tid, approver_id=APPROVER, approver_role="admin")
        with pytest.raises(ApiError) as e:
            await nts.approve_template(template_id=tid, approver_id=APPROVER, approver_role="admin")
        assert e.value.status_code == 409
    finally:
        await _cleanup([tid])


# ── 角色可見性：customer_service 看不到 internal ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_role_visibility_filters_internal():
    assert await db_module._ensure_conn()
    tid = await _mk_template(audience="internal")
    try:
        cs = await nts.list_templates(tenant_id=TID, requester_role="customer_service")
        assert tid not in [i["id"] for i in cs["items"]]      # 看不到 internal
        adm = await nts.list_templates(tenant_id=TID, requester_role="admin")
        assert tid in [i["id"] for i in adm["items"]]         # admin 看得到
    finally:
        await _cleanup([tid])


# ── seed 七類齊全 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_all_seven_template_types_seeded():
    assert await db_module._ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT DISTINCT template_type FROM notification_template WHERE tenant_id IS NULL AND status='approved'")
    types = {r[0] for r in await cur.fetchall()}
    assert {"quote", "payment", "dispatch", "delay", "completion", "rma", "refund"} <= types
