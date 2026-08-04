"""customer_respond_to_quote 的 await 回歸守線（純單元，不需 DB）。

WHY 這個檔案存在：
  2026-07-21（2f5cab17）在 quote_engine_service.py:785 漏了包住 fetchone() 的
  最外層 await。psycopg 的 AsyncCursor.fetchone() 是 coroutine，漏 await 時
  `coroutine or [None]` 因 coroutine 恆為 truthy 而直接取到 coroutine，再 [0]
  就是 TypeError——而且那行在下方 try 之前，等於**整個函式一進來就炸**：
  客戶在 LINE 點「同意報價」/「拒絕」全數失敗。

  既有的 test_cr_0095_quote_line_approval.py 其實測到了這條路徑（冪等回放、
  QUOTE_ALREADY_DECIDED、QUOTE_EXPIRED），但它們是 live DB 的 component test，
  沒有真連線就跑不到，所以 bug 帶著測試一起上線兩週。本檔補的是「**不需要 DB
  也能抓到**」那一層，讓漏 await 這種靜默錯誤在一般 pytest 就會紅。

涵蓋兩層：
  1. 行為層：mock 掉連線，跑冪等回放路徑，確認回得出 dict 而不是 TypeError。
  2. 靜態層：AST 掃 api/ 與 agent/，確認沒有「receiver 是 await…execute(…)
     但 fetch* 本身沒被 await」的呼叫——守的是整類 bug 不是單一行。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from services import quote_engine_service as qes

TID = "00000000-0000-0000-0000-000000000001"
QID = "11111111-1111-1111-1111-111111111111"
LINE_UID = "Utestuser0000"


class _FakeCursor:
    """psycopg AsyncCursor 的最小替身——fetchone 必須是 coroutine，
    否則測不出漏 await（同步 Mock 會讓 bug 版本也通過）。"""

    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row
        self.queries: list[str] = []

    async def execute(self, sql, params=None):
        self.queries.append(sql)
        return _FakeCursor(self._row)


@pytest.mark.asyncio
async def test_customer_respond_idempotent_replay_without_db(monkeypatch):
    """已在 accepted 的報價再點一次「同意」→ 冪等回放，不得拋 TypeError。

    這正是 :785 那行的取值結果所驅動的分支；漏 await 時本測試會以
    `TypeError: 'coroutine' object is not subscriptable` 失敗。
    """
    conn = _FakeConn(("accepted",))

    async def _fake_conn():
        return conn

    async def _fake_owner(*, tenant_id, quote_id):
        return LINE_UID

    monkeypatch.setattr(qes, "_conn", _fake_conn)
    monkeypatch.setattr(qes, "resolve_customer_line_uid", _fake_owner)

    result = await qes.customer_respond_to_quote(
        tenant_id=TID, quote_id=QID, line_user_id=LINE_UID, decision="accept",
    )

    assert result["idempotent_replay"] is True
    assert result["state"] == "accepted"
    assert result["decision"] == "accept"
    # 確認真的讀了 quote.state（而非因例外提早離開）
    assert any("SELECT state FROM quote" in q for q in conn.queries)


@pytest.mark.asyncio
async def test_customer_respond_opposite_decision_conflicts(monkeypatch):
    """已 accepted 卻送 reject → 409 QUOTE_ALREADY_DECIDED（同樣依賴 :785 取值）。"""
    from core.errors import ApiError

    conn = _FakeConn(("accepted",))

    async def _fake_conn():
        return conn

    async def _fake_owner(*, tenant_id, quote_id):
        return LINE_UID

    monkeypatch.setattr(qes, "_conn", _fake_conn)
    monkeypatch.setattr(qes, "resolve_customer_line_uid", _fake_owner)

    with pytest.raises(ApiError) as ei:
        await qes.customer_respond_to_quote(
            tenant_id=TID, quote_id=QID, line_user_id=LINE_UID, decision="reject",
        )
    assert ei.value.error_code == "QUOTE_ALREADY_DECIDED"
    assert ei.value.status_code == 409


# ── 靜態層：整類 bug 的守線 ─────────────────────────────────────────────

_FETCH_METHODS = {"fetchone", "fetchall", "fetchmany"}
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCAN_DIRS = ("api", "agent")
_SKIP_PARTS = {".venv", "node_modules", "__pycache__", "site-packages"}


def _unawaited_async_fetches(path: pathlib.Path) -> list[tuple[int, str]]:
    """找出「receiver 內含 await（⇒ 必是 async cursor）但 fetch* 沒被 await」的呼叫。

    只認 receiver 帶 await 的形狀，是為了避開同步 psycopg 的大量誤報——
    同步連線的 `cur.fetchone()` 本來就不該 await。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    awaited = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)
    }

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in _FETCH_METHODS):
            continue
        if id(node) in awaited:
            continue
        if any(isinstance(n, ast.Await) for n in ast.walk(func.value)):
            found.append((node.lineno, func.attr))
    return found


def test_no_unawaited_async_cursor_fetches():
    """整個 api/ 與 agent/ 不得有漏 await 的 async cursor fetch。

    這種錯誤沒有語法錯、沒有 lint 警告、type checker 也不一定攔得下來，
    只在真的執行到那行才炸——所以用靜態掃描當守線。
    """
    offenders = []
    for d in _SCAN_DIRS:
        base = _REPO_ROOT / d
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            if _SKIP_PARTS & set(py.parts):
                continue
            for lineno, method in _unawaited_async_fetches(py):
                offenders.append(f"{py.relative_to(_REPO_ROOT)}:{lineno} .{method}() 未被 await")

    assert not offenders, (
        "偵測到漏 await 的 async cursor 呼叫（會在執行到該行時拋 "
        "TypeError: 'coroutine' object is not subscriptable）：\n  "
        + "\n  ".join(offenders)
    )
