"""轉真人 / 派工的營運紀錄(escalation log)。

刻意與 per-user 記憶(MemoryStore)分開:escalation 是給營運查的稽核紀錄,
不是要餵回 LLM 的記憶,語意不同。但同樣 scope 在 tenant+user_id(default deny)。
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


def _require_scope(tenant: str, user_id: str) -> None:
    if not tenant or not user_id:
        raise ValueError("escalation 讀寫必須帶 tenant + user_id(default deny)")


@dataclass
class EscalationRecord:
    id: int
    tenant: str
    user_id: str
    reason: str
    is_explicit: bool
    facts_snapshot: dict
    created_at: int


class EscalationStore:
    """轉真人紀錄的 SQLite 後端。傳 ':memory:' 作測試用記憶體 DB。"""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.db_path)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._con.executescript(
            """
            CREATE TABLE IF NOT EXISTS escalation(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                is_explicit INTEGER NOT NULL DEFAULT 0,
                facts_snapshot TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_escalation_user
                ON escalation(tenant, user_id, created_at);
            """
        )
        self._con.commit()

    def log(
        self,
        tenant: str,
        user_id: str,
        reason: str,
        is_explicit: bool,
        facts_snapshot: dict | None = None,
    ) -> int:
        _require_scope(tenant, user_id)
        now = int(time.time())
        cur = self._con.execute(
            "INSERT INTO escalation(tenant,user_id,reason,is_explicit,facts_snapshot,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (
                tenant,
                user_id,
                reason.strip(),
                1 if is_explicit else 0,
                json.dumps(facts_snapshot or {}, ensure_ascii=False),
                now,
            ),
        )
        self._con.commit()
        return int(cur.lastrowid)

    def list_for_user(self, tenant: str, user_id: str, limit: int = 50) -> list[EscalationRecord]:
        _require_scope(tenant, user_id)
        rows = self._con.execute(
            "SELECT * FROM escalation WHERE tenant=? AND user_id=?"
            " ORDER BY created_at DESC LIMIT ?",
            (tenant, user_id, limit),
        )
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: sqlite3.Row) -> EscalationRecord:
        return EscalationRecord(
            id=r["id"],
            tenant=r["tenant"],
            user_id=r["user_id"],
            reason=r["reason"],
            is_explicit=bool(r["is_explicit"]),
            facts_snapshot=json.loads(r["facts_snapshot"] or "{}"),
            created_at=r["created_at"],
        )

    def close(self) -> None:
        self._con.close()
