"""CR-0068 測試計畫覆蓋 Batch 6 — TI-AUDIT-03 audit log sha256 hash chain。

合規紅線：audit_events append-only + hash chain + 篡改偵測。
測法採確定性、隔離（不依賴全域鏈狀態 —— 別的測試會刪 audit_events 製造鏈洞）：
  1. 相鄰兩列鏈接正確（row2.prev_hash == row1.entry_hash）
  2. 每列 entry_hash == 用 service helper 重算（內容未篡改）
  3. 篡改 payload → 重算對不上（偵測得到）
  4. verify_audit_chain 公開 API 結構正確
"""
from __future__ import annotations
import json
import uuid
import pytest
import core.db as db_module
from services import audit_log_service as als
from tests.conftest import audit_privileged_exec  # CR-0164：audit append-only 後特權繞過

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


async def _read_chain_row(eid: str) -> dict:
    cur = await db_module._conn.execute(
        "SELECT event_type, actor_id, actor_role, action, target_type, target_id, "
        "       payload, prev_hash, entry_hash "
        "FROM audit_events WHERE id = %s::uuid", (eid,))
    r = await cur.fetchone()
    return {
        "event_type": r[0], "actor_id": str(r[1]) if r[1] else None, "actor_role": r[2],
        "action": r[3], "target_type": r[4], "target_id": str(r[5]) if r[5] else None,
        "payload": r[6], "prev_hash": r[7], "entry_hash": r[8],
    }


def _recompute(row: dict) -> str:
    payload_canon = (
        json.dumps(row["payload"], ensure_ascii=False, sort_keys=True)
        if row["payload"] is not None else None
    )
    content = als._canonical_audit_content(
        row["event_type"], row["actor_id"], row["actor_role"], row["action"],
        row["target_type"], row["target_id"], payload_canon)
    return als._compute_entry_hash(row["prev_hash"] or als._AUDIT_GENESIS, content)


@pytest.mark.asyncio
async def test_audit_chain_builds_and_links():
    assert await db_module._ensure_conn()
    tgt = str(uuid.uuid4())
    id1 = await als.log_event_returning_id(
        event_type="test_chain", actor_id=None, actor_role="system",
        action="evt1", target_type="test", target_id=tgt, payload={"n": 1, "a": "x"})
    id2 = await als.log_event_returning_id(
        event_type="test_chain", actor_id=None, actor_role="system",
        action="evt2", target_type="test", target_id=tgt, payload={"n": 2})
    try:
        r1, r2 = await _read_chain_row(id1), await _read_chain_row(id2)
        # 鏈接：第二列 prev_hash 接第一列 entry_hash（相鄰插入）
        assert r2["prev_hash"] == r1["entry_hash"]
        # 每列 entry_hash 與重算一致（內容未篡改）
        assert _recompute(r1) == r1["entry_hash"]
        assert _recompute(r2) == r2["entry_hash"]
    finally:
        await audit_privileged_exec(
            "DELETE FROM audit_events WHERE target_id=%s::uuid", (tgt,))


@pytest.mark.asyncio
async def test_audit_chain_detects_payload_tampering():
    assert await db_module._ensure_conn()
    tgt = str(uuid.uuid4())
    eid = await als.log_event_returning_id(
        event_type="test_chain", actor_id=None, actor_role="system",
        action="tamper-me", target_type="test", target_id=tgt, payload={"amount": 100})
    try:
        before = await _read_chain_row(eid)
        assert _recompute(before) == before["entry_hash"]   # 篡改前：一致
        # 直接竄改 payload（模擬攻擊者改數字），entry_hash 不動
        await audit_privileged_exec(
            "UPDATE audit_events SET payload=%s::jsonb WHERE id=%s::uuid",
            (json.dumps({"amount": 999}), eid))
        after = await _read_chain_row(eid)
        assert _recompute(after) != after["entry_hash"]     # 篡改後：重算對不上 → 偵測到
    finally:
        await audit_privileged_exec(
            "DELETE FROM audit_events WHERE target_id=%s::uuid", (tgt,))


@pytest.mark.asyncio
async def test_verify_audit_chain_api_shape():
    assert await db_module._ensure_conn()
    out = await als.verify_audit_chain(limit=50)
    # CR-0184：新增 breaks（所有斷點）＋checkpoint（re-baseline 資訊）；原欄位保留向下相容
    assert set(out.keys()) == {"checked", "valid", "broken_at", "breaks", "checkpoint"}
    assert isinstance(out["checked"], int) and isinstance(out["valid"], bool)
    assert isinstance(out["breaks"], list)
