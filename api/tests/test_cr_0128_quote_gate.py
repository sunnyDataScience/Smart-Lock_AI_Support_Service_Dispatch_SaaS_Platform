"""CR-0128 報價先行 gate（WBS 1.2.1 / ADR-015①② / BR-WO-01）。

- convert gate：無報價/報價進行中 → 425；報價全數失效 → 409；accepted → 201 且回填綁定
- 急件 carve-out：pc.emergency_class 非空 → 跳過報價開單 + 系統建 retrospective_audit_only 佔位
- 補審狀態機：audit_complete → accepted
- 完工硬閘：quote_gate_applied 單須有 accepted 報價；存量單（FALSE）豁免
- PC 層報價：create_quote(problem_card_id) work_order_id=NULL、版本遞增
- 中央轉移表 ↔ 各 *_FROM 守衛集合對帳（G6 兩邊同步鐵律）
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import seed_accepted_quote

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"

pytestmark = pytest.mark.component


async def _seed_confirmed_pc(emergency_class: str | None = None) -> tuple[str, str]:
    """user（含地址）→conv→confirmed PC。回 (pc_id, uid)。"""
    await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'報價閘測試客','0912000128','台北市大安區128號','line_user')",
        (uid, TID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')",
        (cid, uid, "sess-" + pid[:12]),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent, emergency_class) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed','repair',%s)",
        (pid, cid, emergency_class),
    )
    return pid, uid


async def _cleanup(uid: str, pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── convert gate ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convert_no_quote_425():
    pid, uid = await _seed_confirmed_pc()
    try:
        with pytest.raises(ApiError) as ei:
            await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert ei.value.status_code == 425
        assert ei.value.error_code == "QUOTE_NOT_CUSTOMER_CONFIRMED"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_convert_pending_quote_425():
    """報價存在但僅 sent（客戶未確認）→ 仍 425。"""
    pid, uid = await _seed_confirmed_pc()
    try:
        await db_module._conn.execute(
            "INSERT INTO quote (problem_card_id, state, tenant_id, version) "
            "VALUES (%s::uuid,'sent',%s::uuid,1)", (pid, TID))
        with pytest.raises(ApiError) as ei:
            await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert ei.value.status_code == 425
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_convert_dead_quotes_409():
    """報價全數失效（rejected/expired）→ 409 QUOTE_STATE_INVALID。"""
    pid, uid = await _seed_confirmed_pc()
    try:
        await db_module._conn.execute(
            "INSERT INTO quote (problem_card_id, state, tenant_id, version) "
            "VALUES (%s::uuid,'rejected',%s::uuid,1), (%s::uuid,'expired',%s::uuid,2)",
            (pid, TID, pid, TID))
        with pytest.raises(ApiError) as ei:
            await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert ei.value.status_code == 409
        assert ei.value.error_code == "QUOTE_STATE_INVALID"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_convert_accepted_quote_ok_and_binds():
    """accepted 報價 → 開單成功；PC 階段報價回填 work_order_id；quote_gate_applied=TRUE。"""
    pid, uid = await _seed_confirmed_pc()
    try:
        qid = await seed_accepted_quote(pid, TID)
        wo, created = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert created is True
        row = await (await db_module._conn.execute(
            "SELECT work_order_id FROM quote WHERE id=%s::uuid", (qid,))).fetchone()
        assert row and str(row[0]) == wo["id"], "PC 階段報價應回填綁定工單"
        gate = await (await db_module._conn.execute(
            "SELECT quote_gate_applied FROM work_orders WHERE id=%s::uuid", (wo["id"],))).fetchone()
        assert gate and gate[0] is True
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_convert_emergency_carveout_creates_audit_placeholder():
    """急件（emergency_class 非空）跳過報價開單；系統建 retrospective_audit_only 佔位。"""
    pid, uid = await _seed_confirmed_pc(emergency_class="locked_out")
    try:
        wo, created = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert created is True
        row = await (await db_module._conn.execute(
            "SELECT state FROM quote WHERE work_order_id=%s::uuid", (wo["id"],))).fetchone()
        assert row and row[0] == "retrospective_audit_only"
    finally:
        await _cleanup(uid, pid)


# ── 補審狀態機 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_complete_transition():
    pid, uid = await _seed_confirmed_pc(emergency_class="trapped_inside")
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        qrow = await (await db_module._conn.execute(
            "SELECT id FROM quote WHERE work_order_id=%s::uuid", (wo["id"],))).fetchone()
        out = await qe.transition(tenant_id=TID, quote_id=str(qrow[0]), action="audit_complete")
        assert out["state"] == "accepted"
    finally:
        await _cleanup(uid, pid)


# ── 完工硬閘（ADR-015②）─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_completion_gate_blocks_unaudited_emergency(monkeypatch):
    """急件單補審未完成（佔位報價未 accepted）→ 完工 422 QUOTE_NOT_CONFIRMED_FOR_CLOSE。"""
    from services import config_m18_service

    async def _cfg(*, namespace, key="default"):
        if namespace == "completion_policy":
            return {"min_photos": 0, "require_signature": False}
        return None
    monkeypatch.setattr(config_m18_service, "read_global_value", _cfg)

    pid, uid = await _seed_confirmed_pc(emergency_class="safety_risk")
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        await db_module._conn.execute(
            "UPDATE work_orders SET status='accepted' WHERE id=%s::uuid", (wo["id"],))
        with pytest.raises(ApiError) as ei:
            await svc.complete_order(
                tenant_id=TID, wo_id=wo["id"], summary="測試完工",
                photo_evidence_ids=[], signature_evidence_id=None, is_override=False)
        assert ei.value.error_code == "QUOTE_NOT_CONFIRMED_FOR_CLOSE"
        # 補審完成 → 同樣路徑不再被 quote 閘擋（可能被其他閘擋，故只驗不再是本閘）
        qrow = await (await db_module._conn.execute(
            "SELECT id FROM quote WHERE work_order_id=%s::uuid", (wo["id"],))).fetchone()
        await qe.transition(tenant_id=TID, quote_id=str(qrow[0]), action="audit_complete")
        try:
            await svc.complete_order(
                tenant_id=TID, wo_id=wo["id"], summary="測試完工",
                photo_evidence_ids=[], signature_evidence_id=None, is_override=False)
        except ApiError as exc:
            assert exc.error_code != "QUOTE_NOT_CONFIRMED_FOR_CLOSE"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_completion_gate_grandfathers_legacy_wo(monkeypatch):
    """存量單（quote_gate_applied=FALSE，直接 SQL 建）完工不驗報價（D3a 豁免）。"""
    from services import config_m18_service

    async def _cfg(*, namespace, key="default"):
        if namespace == "completion_policy":
            return {"min_photos": 0, "require_signature": False}
        return None
    monkeypatch.setattr(config_m18_service, "read_global_value", _cfg)

    pid, uid = await _seed_confirmed_pc()
    wid = str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, tenant_id) "
            "VALUES (%s::uuid,%s::uuid,'accepted','台北市大安區128號',%s::uuid)",
            (wid, pid, TID))
        out = await svc.complete_order(
            tenant_id=TID, wo_id=wid, summary="存量單完工",
            photo_evidence_ids=[], signature_evidence_id=None, is_override=False)
        assert out  # 未被 QUOTE_NOT_CONFIRMED_FOR_CLOSE 擋下
    finally:
        await _cleanup(uid, pid)


# ── PC 層報價 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_quote_at_pc_stage_and_versioning():
    pid, uid = await _seed_confirmed_pc()
    try:
        q1 = await qe.create_quote(tenant_id=TID, problem_card_id=pid)
        q2 = await qe.create_quote(tenant_id=TID, problem_card_id=pid)
        assert q1["work_order_id"] is None
        assert (q1["version"], q2["version"]) == (1, 2)
        lst = await qe.list_pc_quotes(tenant_id=TID, problem_card_id=pid)
        assert [x["version"] for x in lst] == [2, 1]
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_create_quote_requires_binding():
    with pytest.raises(ApiError) as ei:
        await qe.create_quote(tenant_id=TID)
    assert ei.value.status_code == 422


# ── G6 中央轉移表 ↔ 守衛集合對帳 ─────────────────────────────────────────────

def test_wo_transitions_consistent_with_guards():
    """_WO_TRANSITIONS 為正典，各 *_FROM 守衛集合是逐動作投影——兩邊必須同步。"""
    t = svc._WO_TRANSITIONS
    for st in svc._ASSIGN_FROM:
        assert "assigned" in t[st], f"assign: {st}"
    for st in svc._ACCEPT_FROM:
        assert "accepted" in t[st], f"accept: {st}"
    for st in svc._COMPLETE_FROM:
        assert "completed" in t[st], f"complete: {st}"
    for st in svc._CANCEL_FROM:
        assert "cancelled" in t[st], f"cancel: {st}"
    for st in svc._CONFIRM_FROM:
        assert "confirmed" in t[st], f"confirm: {st}"
    for st in svc._REASSIGN_FROM:
        assert "assigned" in t[st], f"reassign: {st}"
    # 終局狀態無出邊
    assert t["confirmed"] == set() and t["cancelled"] == set()
