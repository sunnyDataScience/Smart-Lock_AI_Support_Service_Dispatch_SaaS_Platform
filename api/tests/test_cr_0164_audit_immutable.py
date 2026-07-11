"""CR-0164 A：audit_events append-only trigger（migration 100）+ verify 端點接線。

- trigger：一般 UPDATE/DELETE 被擋（append-only 物理強制，NFR-Aud-001）。
- verify 端點：把既有 verify_audit_chain 接上 API（原死機制）→ 可偵測竄改。
"""

from __future__ import annotations

import json
import uuid

import pytest

import core.db as db_module
from services import audit_log_service as als
from tests.conftest import DEFAULT_TENANT_ID, audit_privileged_exec

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID
VERIFY_PATH = f"/tenants/{TID}/audit/verify"
CROSS_VERIFY = "/tenants/ffffffff-ffff-4fff-bfff-ffffffffffff/audit/verify"


@pytest.mark.asyncio
async def test_trigger_blocks_update_and_delete():
    """一般 UPDATE/DELETE audit_events → append-only trigger RAISE。"""
    assert await db_module._ensure_conn()
    tgt = str(uuid.uuid4())
    eid = await als.log_event_returning_id(
        event_type="test", actor_id=None, actor_role="system",
        action="immutable-check", target_type="test", target_id=tgt, payload={"n": 1})
    try:
        with pytest.raises(Exception) as ue:
            await db_module._conn.execute(
                "UPDATE audit_events SET action='hacked' WHERE id=%s::uuid", (eid,))
        assert "append-only" in str(ue.value).lower()
        # UPDATE 失敗會讓連線進 aborted 交易；autocommit 下需 rollback 復原
        await db_module._conn.execute("ROLLBACK")
        with pytest.raises(Exception) as de:
            await db_module._conn.execute(
                "DELETE FROM audit_events WHERE id=%s::uuid", (eid,))
        assert "append-only" in str(de.value).lower()
        await db_module._conn.execute("ROLLBACK")
    finally:
        await audit_privileged_exec("DELETE FROM audit_events WHERE target_id=%s::uuid", (tgt,))


@pytest.mark.asyncio
async def test_verify_endpoint_shape_and_auth(client, admin_headers):
    """verify 端點 200 + {checked,valid,broken_at}；cross-tenant 403。"""
    r = await client.get(VERIFY_PATH, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data.keys()) == {"checked", "valid", "broken_at"}
    assert isinstance(data["checked"], int) and isinstance(data["valid"], bool)

    rc = await client.get(CROSS_VERIFY, headers=admin_headers)
    assert rc.status_code == 403


@pytest.mark.asyncio
async def test_verify_detects_privileged_tampering():
    """特權繞過注入竄改（模擬 DBA 級攻擊）→ verify 仍偵測到 valid=False。"""
    assert await db_module._ensure_conn()
    tgt = str(uuid.uuid4())
    eid = await als.log_event_returning_id(
        event_type="test", actor_id=None, actor_role="system",
        action="tamper", target_type="test", target_id=tgt, payload={"amount": 100})
    try:
        # 用特權繞過 trigger 改 payload（entry_hash 不動）→ 模擬繞過物理保護的攻擊者
        await audit_privileged_exec(
            "UPDATE audit_events SET payload=%s::jsonb WHERE id=%s::uuid",
            (json.dumps({"amount": 999}), eid))
        out = await als.verify_audit_chain(limit=5000)
        assert out["valid"] is False, "竄改後 verify 應偵測到鏈不完整"
    finally:
        await audit_privileged_exec("DELETE FROM audit_events WHERE target_id=%s::uuid", (tgt,))
