"""CR-0132 問題卡雙 gate schema（WBS 1.2.3 / 15_SDS §4.6 / 18_DB §4.3）。

- 雙完整度：intake（Gate①分流）/ resolution（Gate② RMA spine）分開計算與持久化
- knowledge_ready：spine 補齊自動翻 TRUE（精煉汲取條件）；operational 結案不被 Gate② 擋
- 待補知識佇列：resolved 且未 ready 入列、補齊後出列
- Gate① enforce：config 開關（預設 off 沿用現行；on 時 confirm 缺分流欄 → 422 INTAKE_GATE_UNMET）
- tenant_id 直欄：建卡（人工/AI 起草）即寫入
"""
from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import problem_card_service as pcs

TID = "00000000-0000-0000-0000-000000000001"

pytestmark = pytest.mark.component


async def _seed_conv() -> tuple[str, str]:
    await db_module._ensure_conn()
    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'雙閘測試客','0912000132','台北市信義區132號','line_user')",
        (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + cid[:12]))
    return cid, uid


async def _cleanup(uid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM problem_cards WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=%s::uuid)",
        (uid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


async def _mk_card(cid: str) -> str:
    card = await pcs.create_card(
        tenant_id=TID, conversation_id=cid, brand="Yale", model="YDM",
        symptom="門鎖異響", urgency="medium")
    return card["id"]


@pytest.mark.asyncio
async def test_tenant_id_written_on_create():
    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)
        row = await (await db_module._conn.execute(
            "SELECT tenant_id FROM problem_cards WHERE id=%s::uuid", (pc_id,))).fetchone()
        assert row and str(row[0]) == TID
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_dual_scores_progressive_and_knowledge_ready():
    """漸進補寫：分流欄補齊 → intake=1.0；spine 補齊 → resolution=1.0 且 knowledge_ready。"""
    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)
        card = await pcs.get_card(tenant_id=TID, pc_id=pc_id)
        assert card["intake_completeness"] is not None and card["intake_completeness"] < 1.0
        assert card["knowledge_ready"] is False

        # Gate①：補分流欄
        card = await pcs.update_card(
            tenant_id=TID, pc_id=pc_id, contact_phone="0912000132",
            failure_mode="motor_stuck", triage_tier="L2")
        assert card["intake_completeness"] == 1.0, card["intake_completeness"]
        assert card["resolution_completeness"] < 1.0

        # Gate②：補 RMA spine（resolution_channel/resolved_by 由 resolve 落）
        await pcs.confirm_card(tenant_id=TID, pc_id=pc_id)
        await pcs.resolve_card(tenant_id=TID, pc_id=pc_id, resolution_layer="L2",
                               resolved_by=str(uuid.uuid4()))
        card = await pcs.update_card(
            tenant_id=TID, pc_id=pc_id, root_cause="馬達卡齒輪",
            root_cause_category="mechanical", corrective_action="更換馬達模組並潤滑",
            verification=True, disposition="repair")
        assert card["resolution_completeness"] == 1.0, card
        assert card["knowledge_ready"] is True
        assert card["resolution_channel"] == "line_text_cs"  # L2 預設映射
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_l3_requires_location_and_hw_fields():
    """L3 條件必填：Gate① 加 location、Gate② 加 firmware/serial。"""
    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)
        card = await pcs.update_card(
            tenant_id=TID, pc_id=pc_id, contact_phone="0912",
            failure_mode="lock_fail", triage_tier="L3")
        assert card["intake_completeness"] < 1.0, "L3 缺 location 不應滿分"
        await db_module._conn.execute(
            "UPDATE problem_cards SET location='台北市信義區132號' WHERE id=%s::uuid", (pc_id,))
        card = await pcs.update_card(tenant_id=TID, pc_id=pc_id, root_cause="x",
                                     root_cause_category="hw", corrective_action="y",
                                     verification=True, disposition="onsite_service",
                                     resolution_channel="onsite")
        assert card["intake_completeness"] == 1.0
        assert card["resolution_completeness"] < 1.0, "L3 缺 firmware/serial/resolved_by 不應滿分"
        card = await pcs.update_card(tenant_id=TID, pc_id=pc_id,
                                     firmware_version="1.2.3", serial="SN-132")
        assert card["knowledge_ready"] is False  # 還缺 resolved_by
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_knowledge_queue_lists_then_clears():
    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)
        await pcs.confirm_card(tenant_id=TID, pc_id=pc_id)
        await pcs.resolve_card(tenant_id=TID, pc_id=pc_id, resolution_layer="L1",
                               resolved_by=str(uuid.uuid4()))
        q = await pcs.list_knowledge_queue(tenant_id=TID)
        assert any(x["id"] == pc_id for x in q), "resolved 未 ready 應入待補知識佇列"

        await pcs.update_card(tenant_id=TID, pc_id=pc_id, root_cause="誤操作",
                              root_cause_category="user_error", corrective_action="教學導引",
                              verification=True, disposition="user_education")
        q = await pcs.list_knowledge_queue(tenant_id=TID)
        assert not any(x["id"] == pc_id for x in q), "Gate② 過後應出列"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_gate1_enforce_config_switch(monkeypatch):
    """gate1_enforce=on：confirm 缺分流欄 → 422 INTAKE_GATE_UNMET；補齊後過。預設 off 不擋。"""
    from services import config_m18_service

    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)

        async def _cfg_on(*, namespace, key="default"):
            if namespace == "problemcard_policy":
                return {"gate1_enforce": True}
            return None
        monkeypatch.setattr(config_m18_service, "read_global_value", _cfg_on)
        with pytest.raises(ApiError) as ei:
            await pcs.confirm_card(tenant_id=TID, pc_id=pc_id)
        assert ei.value.error_code == "INTAKE_GATE_UNMET"

        await pcs.update_card(tenant_id=TID, pc_id=pc_id, contact_phone="0912000132",
                              failure_mode="battery_drain", triage_tier="L1")
        card = await pcs.confirm_card(tenant_id=TID, pc_id=pc_id)
        assert card["status"] == "confirmed"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_enum_validation():
    cid, uid = await _seed_conv()
    try:
        pc_id = await _mk_card(cid)
        for kw in ({"triage_tier": "L9"}, {"resolution_channel": "fax"}, {"disposition": "explode"}):
            with pytest.raises(ApiError) as ei:
                await pcs.update_card(tenant_id=TID, pc_id=pc_id, **kw)
            assert ei.value.status_code == 422
    finally:
        await _cleanup(uid)
