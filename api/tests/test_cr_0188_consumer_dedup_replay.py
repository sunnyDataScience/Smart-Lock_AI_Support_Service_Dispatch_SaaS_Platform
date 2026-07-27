"""CR-0188：事件消費 dedup 毒藥丸——handler 失敗後投影永久補不回來。

**Bug**：`process_event` 原本先呼叫 `_already_processed`，而該函式是
`INSERT ... ON CONFLICT DO NOTHING` 兼作「查詢＋佔位」。共用連線是
`autocommit=True`（core/db.py），所以 dedup 列在 handler 執行**之前**就已提交。
handler 一旦失敗，該 event_id 就被永久判定為「已處理」→ 重播 no-op →
該筆投影再也補不回來（**不可逆資料遺失**，非競態）。

原始碼註解寫「單事件失敗只 log，不中斷消費（可後續重播）」—— 但重播其實不可能。
這也是讓 BR-SETTLE-05 對帳閘門永遠過不了的根源之一（missing 投影無法自癒）。

**修法**：`_already_processed` 改唯讀，新增 `_mark_processed` 在 handler 成功後才記。
並發重投的窗口以「兩個 handler 皆為 ON CONFLICT DO UPDATE 冪等 upsert」承接。
"""

from __future__ import annotations

import pytest

from realtime import event_consumer as ec


class _FakeCur:
    def __init__(self, row=None, rowcount: int = 1):
        self._row = row
        self.rowcount = rowcount

    async def fetchone(self):
        return self._row


class _FakeConn:
    """記錄所有 SQL；dedup 表以 set 模擬（真實語意：event_id 唯一）。"""

    def __init__(self):
        self.dedup: set[str] = set()
        self.sql_log: list[str] = []

    async def execute(self, sql, args=None):
        self.sql_log.append(sql)
        if "SELECT 1 FROM event_consumer_dedup" in sql:
            return _FakeCur(row=(1,) if args and args[0] in self.dedup else None)
        if "INSERT INTO event_consumer_dedup" in sql:
            eid = args[0] if args else None
            new = eid not in self.dedup
            if new:
                self.dedup.add(eid)
            return _FakeCur(rowcount=1 if new else 0)
        return _FakeCur()


@pytest.fixture
def _conn(monkeypatch):
    conn = _FakeConn()

    async def _fake_tech_conn():
        return conn

    monkeypatch.setattr(ec, "_tech_conn", _fake_tech_conn)
    return conn


_EVENT = {"event_id": "evt-cr0188", "settlement_id": "s1", "tenant_id": "t1",
          "technician_id": "u1", "amount": 100}


@pytest.mark.asyncio
async def test_failed_handler_leaves_event_replayable(_conn, monkeypatch):
    """核心：handler 失敗後**不得**留下 dedup 標記，否則重播永遠 no-op。"""
    calls = {"n": 0}

    async def _boom(conn, event):
        calls["n"] += 1
        raise RuntimeError("模擬 handler 失敗（欄位缺漏／DB 瞬斷）")

    monkeypatch.setitem(ec._HANDLERS, "commission.accrued", _boom)

    ok = await ec.process_event("commission.accrued", _EVENT)
    assert ok is False, "handler 失敗應回 False"
    assert "evt-cr0188" not in _conn.dedup, (
        "handler 失敗卻留下 dedup 標記 → 該事件永久無法重播、投影永久遺失"
    )

    # 重播：必須真的再次執行 handler（修復前這裡會直接被 dedup 擋掉）
    await ec.process_event("commission.accrued", _EVENT)
    assert calls["n"] == 2, "重播未再次觸發 handler → dedup 毒藥丸仍在"


@pytest.mark.asyncio
async def test_successful_handler_marks_dedup_and_blocks_replay(_conn, monkeypatch):
    """成功才標記；標記後重複投遞被擋（dedup 本來的用途不能失效）。"""
    calls = {"n": 0}

    async def _ok(conn, event):
        calls["n"] += 1

    monkeypatch.setitem(ec._HANDLERS, "commission.accrued", _ok)

    assert await ec.process_event("commission.accrued", _EVENT) is True
    assert "evt-cr0188" in _conn.dedup, "成功處理後應留下 dedup 標記"

    assert await ec.process_event("commission.accrued", _EVENT) is False
    assert calls["n"] == 1, "重複投遞不應再次執行 handler"


@pytest.mark.asyncio
async def test_dedup_check_is_read_only(_conn, monkeypatch):
    """檢查階段不得寫入 —— 這正是毒藥丸的成因。"""
    async def _ok(conn, event):
        pass

    monkeypatch.setitem(ec._HANDLERS, "commission.accrued", _ok)
    await ec.process_event("commission.accrued", _EVENT)

    first_dedup_sql = next(s for s in _conn.sql_log if "event_consumer_dedup" in s)
    assert first_dedup_sql.strip().upper().startswith("SELECT"), (
        f"dedup 檢查仍是寫入操作（{first_dedup_sql[:60]}）→ handler 失敗會永久佔位"
    )


@pytest.mark.asyncio
async def test_no_event_id_still_processes(_conn, monkeypatch):
    """無 event_id 的事件仍應被處理（不得因新增標記路徑而回歸）。"""
    async def _ok(conn, event):
        pass

    monkeypatch.setitem(ec._HANDLERS, "commission.accrued", _ok)
    assert await ec.process_event("commission.accrued", {"settlement_id": "s2"}) is True
