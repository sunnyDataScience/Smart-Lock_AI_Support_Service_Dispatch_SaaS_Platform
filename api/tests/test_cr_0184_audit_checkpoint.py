"""CR-0184（UAT-0723-F3）：audit hash-chain re-baseline checkpoint + verify 增強。

根因＝CR-0166 lock 前並發競態造成歷史鏈分叉；業主裁決非破壞式 re-baseline。
測法（component，隔離自清）：插一段含分叉的測試鏈 → verify(全鏈) 偵測斷點並回報所有
斷點 → 建 checkpoint（基準=鏈末）→ verify(checkpoint) 只驗基準後（valid）；teardown 清除。
"""
from __future__ import annotations

import hashlib
import uuid

import pytest

import core.db as db_module
from services import audit_log_service as als
from tests.conftest import audit_privileged_exec

pytestmark = pytest.mark.component

_MARK = "cr0184-itest"


def _h(prev: str, action: str) -> str:
    content = als._canonical_audit_content("admin_action", None, None, action, None, None, None)
    return hashlib.sha256(f"{prev}|{content}".encode()).hexdigest()


async def _ins(prev: str, entry: str, action: str, secs: int) -> None:
    await audit_privileged_exec(
        "INSERT INTO audit_events(event_type, action, prev_hash, entry_hash, created_at) "
        "VALUES ('admin_action', %s, %s, %s, TIMESTAMPTZ '2099-01-01 00:00:00+00' + (%s || ' seconds')::interval)",
        (action, prev, entry, str(secs)),
    )


@pytest.fixture
async def _forked_chain():
    """插 a→b→c + 一條分叉（接 b 而非 c），時戳 2099（不干擾真實鏈驗證起點）。"""
    from core.db import _ensure_conn
    await _ensure_conn()
    g = als._AUDIT_GENESIS
    h1, h2, h3 = _h(g, f"{_MARK}-a"), None, None
    h2 = _h(h1, f"{_MARK}-b")
    h3 = _h(h2, f"{_MARK}-c")
    hf = _h(h2, f"{_MARK}-fork")
    await _ins(g, h1, f"{_MARK}-a", 1)
    await _ins(h1, h2, f"{_MARK}-b", 2)
    await _ins(h2, h3, f"{_MARK}-c", 3)
    await _ins(h2, hf, f"{_MARK}-fork", 4)   # 分叉：又接 h2
    yield {"tip_hash": hf}
    # teardown：清測試列 + 本測試建的 checkpoint
    await audit_privileged_exec("DELETE FROM audit_events WHERE action LIKE %s", (f"{_MARK}%",))
    await audit_privileged_exec("DELETE FROM audit_chain_checkpoint WHERE note = %s", (_MARK,))


@pytest.mark.asyncio
async def test_full_chain_detects_fork_and_reports_all_breaks(_forked_chain):
    r = await als.verify_audit_chain(use_checkpoint=False, limit=10000)
    # 全鏈驗證（含本測試分叉）→ 至少偵測到我們插的那個分叉
    assert r["valid"] is False
    assert isinstance(r["breaks"], list) and len(r["breaks"]) >= 1
    assert r["broken_at"] == r["breaks"][0]


@pytest.mark.asyncio
async def test_checkpoint_rebaselines_and_verify_passes(_forked_chain):
    cp = await als.create_chain_checkpoint(note=_MARK)
    assert cp["baseline_entry_hash"] == _forked_chain["tip_hash"]  # 基準=目前鏈末
    r = await als.verify_audit_chain(use_checkpoint=True, limit=10000)
    # 基準之後無列（或皆乾淨）→ valid；且回報帶 checkpoint 資訊
    assert r["valid"] is True
    assert r["checkpoint"] is not None
    assert r["checkpoint"]["baseline_entry_hash"] == cp["baseline_entry_hash"]


@pytest.mark.asyncio
async def test_verify_after_checkpoint_detects_new_fork(_forked_chain):
    cp = await als.create_chain_checkpoint(note=_MARK)
    tip = cp["baseline_entry_hash"]
    # 基準後接一條乾淨列 + 一條分叉列（又接 tip）
    await _ins(tip, _h(tip, f"{_MARK}-new"), f"{_MARK}-new", 10)
    await _ins(tip, _h(tip, f"{_MARK}-bad"), f"{_MARK}-bad", 11)
    r = await als.verify_audit_chain(use_checkpoint=True, limit=10000)
    assert r["valid"] is False           # 基準後的新分叉被偵測
    assert len(r["breaks"]) >= 1
