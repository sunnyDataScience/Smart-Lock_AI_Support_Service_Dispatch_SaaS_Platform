"""CR-0144:OHS 現場報價修正 command 通道(WBS 2.4.3/ADR-027/TC-DISPATCH-07)。"""

from __future__ import annotations

import os
import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
URL = "/internal/requote-requests"


def _hdr() -> dict:
    return {"X-Internal-Token": os.environ.get("INTERNAL_API_TOKEN", "test-internal-token")}


SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"  # technicians.sql 啟用中技師


async def _mk_wo(status: str = "in_progress") -> tuple[str, str]:
    assert await db_module._ensure_conn()
    wid, tech, pid = str(uuid.uuid4()), SEED_TECH, str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, customer_address, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, '台北市測試路1號', %s::uuid)",
        (wid, pid, status, tech, TID))
    return wid, tech


async def _cleanup(wid: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM requote_requests WHERE work_order_id=%s::uuid", (wid,))
    cur = await db_module._conn.execute(
        "DELETE FROM work_orders WHERE id=%s::uuid RETURNING problem_card_id", (wid,))
    row = await cur.fetchone()
    if row and row[0]:
        await db_module._conn.execute(
            "DELETE FROM quote WHERE problem_card_id=%s::uuid", (row[0],))
        await db_module._conn.execute(
            "DELETE FROM problem_cards WHERE id=%s::uuid", (row[0],))


def _body(wid: str, tech: str, **over) -> dict:
    return {"request_id": f"rq-{uuid.uuid4().hex[:10]}", "work_order_id": wid,
            "technician_id": tech, "reason": "scope_add",
            "item_diffs": [{"item": "鎖芯更換", "qty": 1}], **over}


@pytest.mark.asyncio
async def test_command_creates_quote_v_plus_1_and_replays(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    wid, tech = await _mk_wo()
    try:
        body = _body(wid, tech)
        r1 = await client.post(URL, json=body, headers=_hdr())
        assert r1.status_code == 201, r1.text
        d1 = r1.json()["data"]
        assert d1["status"] == "quoted" and d1["created_quote_id"]

        # 冪等回放:同 request_id → 200 同結果不重建
        r2 = await client.post(URL, json=body, headers=_hdr())
        assert r2.status_code == 200
        assert r2.json()["data"]["created_quote_id"] == d1["created_quote_id"]
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM quote WHERE work_order_id=%s::uuid", (wid,))
        assert (await cur.fetchone())[0] == 1

        # 不同 request_id 但同工單 open → 409
        r3 = await client.post(URL, json=_body(wid, tech), headers=_hdr())
        assert r3.status_code == 409
    finally:
        await _cleanup(wid)


@pytest.mark.asyncio
async def test_supersedes_chain_on_existing_quote(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    wid, tech = await _mk_wo()
    try:
        from services import quote_engine_service
        q1 = await quote_engine_service.create_quote(tenant_id=TID, work_order_id=wid)
        r = await client.post(URL, json=_body(wid, tech), headers=_hdr())
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["supersedes_quote_id"] == str(q1["id"]), "v+1 須串鏈前版"
        cur = await db_module._conn.execute(
            "SELECT supersedes_quote_id::text, version FROM quote WHERE id=%s::uuid",
            (d["created_quote_id"],))
        row = await cur.fetchone()
        assert row[0] == str(q1["id"]) and row[1] == q1["version"] + 1
    finally:
        await _cleanup(wid)


@pytest.mark.asyncio
async def test_403_non_assignee_and_wrong_status(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    wid, tech = await _mk_wo()
    wid2, tech2 = await _mk_wo(status="accepted")
    try:
        r = await client.post(URL, json=_body(wid, str(uuid.uuid4())), headers=_hdr())
        assert r.status_code == 403, "非 assignee 須 403"
        r = await client.post(URL, json=_body(wid2, tech2), headers=_hdr())
        assert r.status_code == 403, "非 in_progress 須 403"
    finally:
        await _cleanup(wid)
        await _cleanup(wid2)


@pytest.mark.asyncio
async def test_internal_token_required_and_cs_fallback_audit(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    wid, tech = await _mk_wo()
    try:
        r = await client.post(URL, json=_body(wid, tech))  # 無 token
        assert r.status_code in (401, 403)

        r = await client.post(URL, json=_body(wid, tech, initiated_via="cs_fallback"),
                              headers=_hdr())
        assert r.status_code == 201
        assert r.json()["data"]["initiated_via"] == "cs_fallback"
    finally:
        await _cleanup(wid)


# ── browser 入口(technician 本人/cs_fallback 代發起,CR-0144 續) ─────────────

SEED_TECH_USER = "66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01"  # technicians.sql 對應 users 列


def _bearer(user_id: str, role: str) -> dict:
    from tests.conftest import _make_token
    return {"Authorization": f"Bearer {_make_token(user_id=user_id, role=role)}",
            "X-Tenant-ID": TID, "Idempotency-Key": f"ik-{uuid.uuid4().hex[:10]}"}


@pytest.mark.asyncio
async def test_tech_browser_entry_and_cs_fallback(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    wid, _ = await _mk_wo()
    try:
        url = f"/tenants/{TID}/work-orders/{wid}/requote-requests"
        # 技師本人(seed 技師的 users 列)
        r = await client.post(url, json={"reason": "scope_add",
                                         "item_diffs": [{"item": "鎖芯", "quantity": 1}]},
                              headers=_bearer(SEED_TECH_USER, "technician"))
        assert r.status_code == 201, r.text
        assert r.json()["data"]["initiated_via"] == "technician_command"
    finally:
        await _cleanup(wid)

    wid2, _ = await _mk_wo()
    try:
        url = f"/tenants/{TID}/work-orders/{wid2}/requote-requests"
        # 後台客服代發起 → cs_fallback 降級標記
        r = await client.post(url, json={"reason": "estimate_error", "item_diffs": []},
                              headers=_bearer(str(uuid.uuid4()), "customer_service"))
        assert r.status_code == 201, r.text
        assert r.json()["data"]["initiated_via"] == "cs_fallback"

        # vendor 不可打(TECH_ACTION 白名單外)
        r = await client.post(url, json={"reason": "scope_add", "item_diffs": []},
                              headers=_bearer(str(uuid.uuid4()), "vendor"))
        assert r.status_code == 403
    finally:
        await _cleanup(wid2)
