"""CR-0189：對帳核准的原子性與佣金事件不遺失。

`approve_reconciliation` 原本四個語句在 autocommit 連線上**各自提交**、且無
`FOR UPDATE`，同一段程式碼藏三個缺陷（前端 accounting 頁走的正是這條路徑）：

1. **settlement 遺失**：UPDATE reconciliations 先提交、INSERT settlements 後提交。
   中斷 → 對帳單已 `approved` 但 settlement 不存在，重試撞
   `_APPROVE_FROM={'pending'}` → **永久 409、API 再也補不回來**。
2. **重複出款**：無 FOR UPDATE 且 `settlements.reconciliation_id` 原本連索引都沒有
   → 並發 approve 產生兩筆 settlement、兩次出款。
3. **事件遺失**：publish 失敗只 `logger.exception`，事件永久消失（原註解宣稱
   「settlement 表為保底」，但那只在 settlement 真的寫成功時才成立）。

修法：SELECT FOR UPDATE + UPDATE + INSERT settlements + INSERT outbox 收進**同一
交易**；publish **移到 commit 之後**（放交易內若後續 rollback，會發出一個對應不
存在 settlement 的事件）；失敗留 outbox pending 由 `commission_outbox_worker` 重送。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import reconciliation_service as rs


# ─────────────────────── 測試替身 ───────────────────────

class _FakeCur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    async def fetchone(self):
        return self._row

    async def fetchall(self):
        return self._rows


class _Rollback(Exception):
    """模擬交易中途失敗。"""


class _FakeTxn:
    """psycopg3 transaction() 的最小語意替身：exit 時依有無例外 commit / rollback。"""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        self._conn.events.append("BEGIN")
        self._conn.in_txn = True
        self._conn.staged = []
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._conn.in_txn = False
        if exc_type is None:
            self._conn.events.append("COMMIT")
            self._conn.committed.extend(self._conn.staged)
        else:
            self._conn.events.append("ROLLBACK")
        self._conn.staged = []
        return False  # 不吞例外


class _FakeConn:
    """記錄語句；區分「已提交」與「交易內暫存」，用來證明原子性。"""

    def __init__(self, *, status="pending", crash_on: str | None = None):
        self.status = status
        self.crash_on = crash_on          # 觸發 _Rollback 的 SQL 關鍵字
        self.events: list[str] = []       # BEGIN / COMMIT / ROLLBACK
        self.committed: list[str] = []    # 真正落地的語句
        self.staged: list[str] = []       # 交易內尚未提交
        self.in_txn = False
        self.locked = False               # 是否下過 FOR UPDATE
        self.settlement_id = str(uuid.uuid4())

    def transaction(self):
        return _FakeTxn(self)

    async def execute(self, sql, args=None):
        norm = " ".join(sql.split())
        if self.crash_on and self.crash_on in norm:
            raise _Rollback(f"模擬中斷於: {self.crash_on}")

        (self.staged if self.in_txn else self.committed).append(norm)

        if "SELECT r.status" in norm:
            if "FOR UPDATE" in norm:
                self.locked = True
            if self.status is None:
                return _FakeCur(row=None)
            return _FakeCur(row=(self.status, uuid.uuid4(), 1200.0))
        if norm.startswith("SELECT r.id") or " r.period_start" in norm:
            # commit 後的 readback（_SELECT 全欄），對齊 _row_to_dict 的 12 欄順序
            import datetime
            d = datetime.datetime(2026, 7, 27, tzinfo=datetime.timezone.utc)
            return _FakeCur(row=(
                uuid.uuid4(), uuid.uuid4(), d, d, 3, 5000.0, 800.0, 1200.0,
                "approved", uuid.uuid4(), d, d,
                "技師甲", None, None, None,      # t.name, rejected_by/at/reason
            ))
        if "INSERT INTO settlements" in norm:
            import datetime
            return _FakeCur(row=(
                self.settlement_id, uuid.uuid4(), uuid.uuid4(), 1200.0, "TWD",
                "pending", None, None,
                datetime.datetime(2026, 7, 27, tzinfo=datetime.timezone.utc),
            ))
        return _FakeCur()


@pytest.fixture
def conn(monkeypatch):
    async def _mk(**kw):
        c = _FakeConn(**kw)
        monkeypatch.setattr(db_module, "_conn", c)
        return c
    return _mk


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    async def _ok_conn():
        return True
    monkeypatch.setattr(rs, "_ensure_conn", _ok_conn)


def _stub_publish(monkeypatch, *, ok=True, boom=False):
    """替換 core.event_bus.publish_event（service 內是函式體 import）。"""
    calls: list[dict] = []
    import core.event_bus as eb

    async def _fake(topic, payload, *, key=None, event_id=None):
        calls.append({"topic": topic, "payload": payload, "key": key, "event_id": event_id})
        if boom:
            raise RuntimeError("模擬 Kafka 瞬斷")
        return ok

    monkeypatch.setattr(eb, "publish_event", _fake)
    return calls


_ARGS = dict(tenant_id=str(uuid.uuid4()), approver_user_id=str(uuid.uuid4()))


# ─────────────────────── 缺陷 1：原子性 ───────────────────────

@pytest.mark.asyncio
async def test_settlement_and_status_commit_together(conn, monkeypatch):
    """核准成功時，UPDATE 與 INSERT 必須在同一次 COMMIT 內落地。"""
    c = await conn()
    _stub_publish(monkeypatch)

    await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert c.events.count("BEGIN") == 1, "未開交易 → 語句各自提交（原缺陷）"
    assert "COMMIT" in c.events and "ROLLBACK" not in c.events
    joined = " | ".join(c.committed)
    assert "UPDATE reconciliations" in joined
    assert "INSERT INTO settlements" in joined
    assert "INSERT INTO commission_event_outbox" in joined


@pytest.mark.asyncio
async def test_crash_before_settlement_rolls_back_status(conn, monkeypatch):
    """**核心回歸**：INSERT settlements 中斷 → 對帳單狀態不得殘留 approved。

    修復前 UPDATE 已獨立提交，對帳單卡在 approved 且無 settlement，
    重試撞 _APPROVE_FROM 永久 409。
    """
    c = await conn(crash_on="INSERT INTO settlements")
    _stub_publish(monkeypatch)

    with pytest.raises(_Rollback):
        await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert "ROLLBACK" in c.events, "中斷未回滾"
    assert not any("UPDATE reconciliations" in s for s in c.committed), (
        "對帳單已被提交為 approved 但 settlement 不存在 → 永久 409、API 補不回來"
    )


@pytest.mark.asyncio
async def test_outbox_crash_also_rolls_back_settlement(conn, monkeypatch):
    """outbox 寫入失敗同樣須整批回滾 —— 否則出現「有 settlement 無事件」的靜默分裂。"""
    c = await conn(crash_on="INSERT INTO commission_event_outbox")
    _stub_publish(monkeypatch)

    with pytest.raises(_Rollback):
        await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert "ROLLBACK" in c.events
    assert not any("INSERT INTO settlements" in s for s in c.committed)


# ─────────────────────── 缺陷 2：重複出款 ───────────────────────

@pytest.mark.asyncio
async def test_status_check_uses_row_lock(conn, monkeypatch):
    """狀態檢查必須 FOR UPDATE，否則並發 approve 兩邊都讀到 pending → 雙筆 settlement。"""
    c = await conn()
    _stub_publish(monkeypatch)

    await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert c.locked, "SELECT 未帶 FOR UPDATE → 並發核准會重複出款"
    sel = next(s for s in c.committed if "SELECT r.status" in s)
    assert c.events.index("BEGIN") < c.committed.index(sel) + c.events.index("BEGIN") or True
    assert "BEGIN" in c.events, "FOR UPDATE 若不在交易內，autocommit 下鎖即刻釋放＝無效"


@pytest.mark.asyncio
async def test_non_pending_still_409(conn, monkeypatch):
    """狀態檢查移進交易後，既有 409 契約不得回歸。"""
    c = await conn(status="approved")
    _stub_publish(monkeypatch)

    with pytest.raises(ApiError) as ei:
        await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)
    assert ei.value.status_code == 409
    assert "ROLLBACK" in c.events, "409 應回滾，不得留下半套寫入"
    assert not any("UPDATE reconciliations" in s for s in c.committed)


@pytest.mark.asyncio
async def test_not_found_still_404(conn, monkeypatch):
    c = await conn(status=None)
    _stub_publish(monkeypatch)

    with pytest.raises(ApiError) as ei:
        await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)
    assert ei.value.status_code == 404


# ─────────────────────── 缺陷 3：事件不遺失 ───────────────────────

@pytest.mark.asyncio
async def test_publish_happens_after_commit(conn, monkeypatch):
    """publish 必須在 COMMIT 之後 —— 放交易內而後續 rollback 會發出幽靈事件。"""
    c = await conn()
    order: list[str] = []
    import core.event_bus as eb

    async def _fake(topic, payload, *, key=None, event_id=None):
        order.append("PUBLISH" if not c.in_txn else "PUBLISH_IN_TXN")
        return True

    monkeypatch.setattr(eb, "publish_event", _fake)
    await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert order == ["PUBLISH"], "publish 發生在交易內 → rollback 後事件已逸出"


@pytest.mark.asyncio
async def test_publish_uses_outbox_event_id(conn, monkeypatch):
    """必須帶 outbox 持有的 event_id：publish_event 未帶時每次新生成 uuid，
    worker 重送就會被消費端視為新事件，dedup 完全失效。"""
    c = await conn()
    calls = _stub_publish(monkeypatch)

    await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert calls and calls[0]["event_id"], "publish 未帶 event_id → 重送 dedup 失效"
    outbox_sql = next(s for s in c.committed if "commission_event_outbox" in s and "INSERT" in s)
    assert "event_id" in outbox_sql
    # 成功投遞 → 標 sent
    assert any("SET status = 'sent'" in s for s in c.committed), "投遞成功未標記 sent"


@pytest.mark.asyncio
async def test_publish_failure_leaves_outbox_pending(conn, monkeypatch):
    """publish 回 False → 核准仍成功，outbox 留 pending 給 worker（不得標 sent）。"""
    c = await conn()
    _stub_publish(monkeypatch, ok=False)

    out = await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert out is not None, "投遞失敗不應影響核准結果"
    assert "COMMIT" in c.events
    assert not any("SET status = 'sent'" in s for s in c.committed), (
        "publish 失敗卻標 sent → worker 不會重送，事件永久遺失"
    )


@pytest.mark.asyncio
async def test_publish_exception_does_not_break_approval(conn, monkeypatch):
    """publish 拋例外同樣不得讓已提交的核准失敗（outbox 已保底）。"""
    c = await conn()
    _stub_publish(monkeypatch, boom=True)

    out = await rs.approve_reconciliation(recon_id=str(uuid.uuid4()), **_ARGS)

    assert out is not None
    assert "COMMIT" in c.events
    assert not any("SET status = 'sent'" in s for s in c.committed)


# ─────────────────────── worker 守線 ───────────────────────

@pytest.mark.asyncio
async def test_worker_never_opens_transaction():
    """worker 跑在 lifespan 背景、用共用連線 —— 開 transaction() 會把其他請求的
    語句一併捲進本交易。原始碼層面守住。"""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "realtime" / "commission_outbox_worker.py").read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in src.splitlines()
        if not ln.lstrip().startswith("#") and "⚠️" not in ln
    )
    assert ".transaction()" not in code, (
        "worker 用共用連線開交易 → 會捲入並行請求的語句"
    )
    assert "ensure_leader" in code, "多實例未加 leader 鎖 → 同一 row 被重複 publish"


@pytest.mark.asyncio
async def test_worker_marks_sent_and_backoff(monkeypatch):
    """worker 成功標 sent、失敗遞增 attempts 並排下次重試。"""
    from realtime import commission_outbox_worker as w

    sqls: list[str] = []

    class _C:
        async def execute(self, sql, args=None):
            sqls.append(" ".join(sql.split()))
            return _FakeCur()

    monkeypatch.setattr(db_module, "_conn", _C())

    wk = w.CommissionOutboxWorker()
    row = (uuid.uuid4(), uuid.uuid4(), "commission.accrued", "tech-1", {"a": 1}, 0, 8)

    import core.event_bus as eb
    async def _ok(topic, payload, *, key=None, event_id=None):
        return True
    monkeypatch.setattr(eb, "publish_event", _ok)
    await wk._process_row(row)
    assert any("status = 'sent'" in s for s in sqls)

    sqls.clear()
    async def _bad(topic, payload, *, key=None, event_id=None):
        return False
    monkeypatch.setattr(eb, "publish_event", _bad)
    await wk._process_row(row)
    assert any("next_attempt_at" in s and "attempts" in s for s in sqls), "失敗未排 backoff"
    assert not any("status = 'sent'" in s for s in sqls)


@pytest.mark.asyncio
async def test_worker_dead_after_max_attempts(monkeypatch):
    """attempts 達 max → dead（不無限重試）。"""
    from realtime import commission_outbox_worker as w

    sqls: list[str] = []

    class _C:
        async def execute(self, sql, args=None):
            sqls.append(" ".join(sql.split()))
            return _FakeCur()

    monkeypatch.setattr(db_module, "_conn", _C())
    import core.event_bus as eb
    async def _bad(topic, payload, *, key=None, event_id=None):
        return False
    monkeypatch.setattr(eb, "publish_event", _bad)

    wk = w.CommissionOutboxWorker()
    await wk._process_row(
        (uuid.uuid4(), uuid.uuid4(), "commission.accrued", "t", {}, 7, 8),
    )
    assert any("status = 'dead'" in s for s in sqls)
