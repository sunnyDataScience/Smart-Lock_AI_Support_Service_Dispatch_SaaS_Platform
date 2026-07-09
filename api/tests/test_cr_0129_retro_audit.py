"""CR-0129 急件事後補審引擎（WBS 1.2.2 / 15_SDS §4.5 / FR-API-19 / TC-DISPATCH-08）。

- 完工回報起算 4h 補審窗（audit_due_at；D2a：完工可過、結案被擋）
- 補審兩路徑：LIFF（send→accept）與紙本（audit_complete）；一般報價不可繞 audit_complete
- sla_monitor audit_overdue 掃描 + 同租戶連 3 件逾時自動開 ChangeRequest（BR-WO-04）
- URG-01 急件加價 config 覆蓋（D1a）；補審佇列列表；emergency_bypass audit log
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"

pytestmark = pytest.mark.component


def _patch_completion_policy(monkeypatch):
    from services import config_m18_service

    async def _cfg(*, namespace, key="default"):
        if namespace == "completion_policy":
            return {"min_photos": 0, "require_signature": False}
        return None
    monkeypatch.setattr(config_m18_service, "read_global_value", _cfg)


async def _seed_emergency_wo(emergency_class: str = "locked_out") -> tuple[str, str, str]:
    """user→conv→confirmed 急件 PC→convert 開單（佔位報價隨建）。回 (wo_id, pc_id, uid)。"""
    await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'補審測試客','0912000129','台北市中山區129號','line_user')",
        (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent, emergency_class) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','urgent','confirmed','repair',%s)",
        (pid, cid, emergency_class))
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    return wo["id"], pid, uid


async def _cleanup(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(
        f"DELETE FROM quote_approval WHERE quote_id IN (SELECT id FROM quote WHERE work_order_id IN {sub})", (pid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute(
        f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


async def _complete(wid: str) -> None:
    await db_module._conn.execute(
        "UPDATE work_orders SET status='accepted' WHERE id=%s::uuid", (wid,))
    await svc.complete_order(
        tenant_id=TID, wo_id=wid, summary="急件完工",
        photo_evidence_ids=[], signature_evidence_id=None, is_override=False)


async def _placeholder(wid: str):
    return await (await db_module._conn.execute(
        "SELECT id, state, audit_due_at FROM quote WHERE work_order_id=%s::uuid", (wid,))).fetchone()


# ── timer 起算 + D2a 閘門 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_completion_starts_audit_window_and_close_blocked(monkeypatch):
    """急件完工可過（佔位補審中）→ audit_due_at 起算 ≈+4h → 結案被擋 → 補審完成 → 結案過。"""
    _patch_completion_policy(monkeypatch)
    wid, pid, uid = await _seed_emergency_wo()
    try:
        row = await _placeholder(wid)
        assert row[1] == "retrospective_audit_only" and row[2] is None, "完工前不起算"

        await _complete(wid)  # D2a：完工放行
        row = await _placeholder(wid)
        assert row[2] is not None, "完工回報應起算補審窗"
        remain = (row[2] - datetime.now(timezone.utc)).total_seconds()
        assert 3.5 * 3600 < remain <= 4.0 * 3600, f"窗長應 ≈4h（實際 {remain}s）"

        with pytest.raises(ApiError) as ei:
            await svc.confirm_order(tenant_id=TID, wo_id=wid, rating=5)
        assert ei.value.error_code == "QUOTE_NOT_CONFIRMED_FOR_CLOSE"

        await qe.transition(tenant_id=TID, quote_id=str(row[0]), action="audit_complete",
                            comment="紙本簽認：簽單照片 evidence#123")
        out = await svc.confirm_order(tenant_id=TID, wo_id=wid, rating=5)
        assert out["status"] == "closed"  # confirmed → API 讀值 closed
        # 紙本簽認 approval 軌跡
        ap = await (await db_module._conn.execute(
            "SELECT decision FROM quote_approval WHERE quote_id=%s::uuid", (row[0],))).fetchone()
        assert ap and ap[0] == "audit_complete"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_liff_path_send_then_accept(monkeypatch):
    """LIFF 事後確認：補審佔位 → send（放行）→ accept → 結案過。"""
    _patch_completion_policy(monkeypatch)
    wid, pid, uid = await _seed_emergency_wo("trapped_inside")
    try:
        await _complete(wid)
        row = await _placeholder(wid)
        out = await qe.transition(tenant_id=TID, quote_id=str(row[0]), action="send")
        assert out["state"] == "sent"
        out = await qe.transition(tenant_id=TID, quote_id=str(row[0]), action="accept")
        assert out["state"] == "accepted"
        assert (await svc.confirm_order(tenant_id=TID, wo_id=wid, rating=4))["status"] == "closed"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_normal_sent_quote_cannot_audit_complete():
    """一般（非急件）sent 報價不可走 audit_complete 繞過客戶確認 → 409。"""
    await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    qid = str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, display_name, role) "
            "VALUES (%s::uuid,%s::uuid,'一般客','line_user')", (uid, TID))
        await db_module._conn.execute(
            "INSERT INTO conversations (id, user_id, session_id, status) "
            "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + pid[:12]))
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid,%s::uuid,'Yale','YDM','confirmed')", (pid, cid))
        await db_module._conn.execute(
            "INSERT INTO quote (id, problem_card_id, state, tenant_id, version) "
            "VALUES (%s::uuid,%s::uuid,'sent',%s::uuid,1)", (qid, pid, TID))
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=qid, action="audit_complete")
        assert ei.value.status_code == 409
    finally:
        await db_module._conn.execute("DELETE FROM quote WHERE id=%s::uuid", (qid,))
        await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
        await db_module._conn.execute("DELETE FROM conversations WHERE id=%s::uuid", (cid,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── sla_monitor：audit_overdue + 連 3 逾時 CR ────────────────────────────────

@pytest.mark.asyncio
async def test_audit_overdue_scan_and_consecutive_breach_cr(monkeypatch):
    """3 件逾期急件補審 → 掃描告警 + 自動開 emergency_audit_breach CR（不重複開）。"""
    _patch_completion_policy(monkeypatch)
    from realtime.sla_monitor import SLAMonitor

    seeds = []
    try:
        for i in range(3):
            wid, pid, uid = await _seed_emergency_wo("safety_risk")
            seeds.append((pid, uid))
            await _complete(wid)
            # 人工把 due 撥到過去（模擬逾 4h）
            await db_module._conn.execute(
                "UPDATE quote SET audit_due_at = NOW() - INTERVAL '1 hour' "
                "WHERE work_order_id=%s::uuid", (wid,))
        await db_module._conn.execute(
            "DELETE FROM saas.change_request WHERE type_code='emergency_audit_breach'")

        mon = SLAMonitor()
        await mon._scan_once()
        overdue_keys = [k for k in mon._alerted if k[0] == "audit_overdue"]
        assert len(overdue_keys) >= 3, "3 件逾期補審應全數告警"

        cr = await (await db_module._conn.execute(
            "SELECT state FROM saas.change_request "
            "WHERE tenant_id=%s::uuid AND type_code='emergency_audit_breach'", (TID,))).fetchall()
        assert len(cr) == 1 and cr[0][0] == "pending_approval", "連 3 逾時應開唯一一筆 CR"

        await mon._scan_once()  # 再掃不重複開
        cr = await (await db_module._conn.execute(
            "SELECT count(*) FROM saas.change_request "
            "WHERE tenant_id=%s::uuid AND type_code='emergency_audit_breach'", (TID,))).fetchone()
        assert cr[0] == 1
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.change_request WHERE type_code='emergency_audit_breach'")
        for pid, uid in seeds:
            await _cleanup(uid, pid)


# ── 佇列 / 加價 / 稽核軌跡 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_queue_lists_pending_and_overdue(monkeypatch):
    _patch_completion_policy(monkeypatch)
    wid, pid, uid = await _seed_emergency_wo("angry_high_risk")
    try:
        q = await qe.list_audit_queue(tenant_id=TID)
        mine = [x for x in q if x["work_order_id"] == wid]
        assert mine and mine[0]["audit_due_at"] is None, "未完工＝未起算也應入列"
        await _complete(wid)
        q = await qe.list_audit_queue(tenant_id=TID)
        mine = [x for x in q if x["work_order_id"] == wid]
        assert mine and mine[0]["audit_due_at"] is not None and mine[0]["overdue"] is False
        assert mine[0]["emergency_class"] == "angry_high_risk"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_urg01_surcharge_config_override(monkeypatch):
    """URG-01 帶價：目錄 seed 1500；config surcharge_amount 覆蓋（D1a）。"""
    wid, pid, uid = await _seed_emergency_wo()
    try:
        row = await _placeholder(wid)
        qid = str(row[0])
        out = await qe.add_line(tenant_id=TID, quote_id=qid, service_code="URG-01")
        line = [ln for ln in out["lines"] if ln.get("service_code") == "URG-01"][0]
        assert float(line["customer_price"]) == 1500.0, "目錄 seed 初值 1500"

        from services import config_m18_service
        async def _cfg(*, namespace, key="default"):
            if namespace == "emergency_audit_policy":
                return {"surcharge_amount": 2000}
            return None
        monkeypatch.setattr(config_m18_service, "read_global_value", _cfg)
        out = await qe.add_line(tenant_id=TID, quote_id=qid, service_code="URG-01")
        prices = sorted(float(ln["customer_price"]) for ln in out["lines"]
                        if ln.get("service_code") == "URG-01")
        assert prices == [1500.0, 2000.0], "config 覆蓋應生效於新增明細"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.asyncio
async def test_emergency_bypass_audit_logged():
    """急件開單應留 emergency_bypass 稽核軌跡（15_SDS §4.5 步驟1）。"""
    wid, pid, uid = await _seed_emergency_wo()
    try:
        row = await (await db_module._conn.execute(
            "SELECT payload FROM audit_events "
            "WHERE action='emergency_bypass' AND target_id=%s ORDER BY created_at DESC LIMIT 1",
            (wid,))).fetchone()
        assert row, "急件開單應寫 emergency_bypass audit"
    finally:
        await db_module._conn.execute(
            "DELETE FROM audit_events WHERE action='emergency_bypass' AND target_id=%s", (wid,))
        await _cleanup(uid, pid)
