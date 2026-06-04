"""SQLite + FTS5 的 per-user 記憶儲存(DAO)。

核心不變量:**所有讀寫都必須帶 `tenant + user_id`**,否則拒絕(default deny)——
這是多用戶客服隔離的根基,讓上層無法不小心跨 user 查詢。

FTS5 用 trigram tokenizer,支援中文子字串檢索(unicode61 對無空格中文無效)。
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

VALID_KINDS = {"profile", "preference", "fact", "issue", "dispatch"}


@dataclass(frozen=True)
class MemoryEntry:
    id: int
    tenant: str
    user_id: str
    kind: str
    content: str
    source_session: str | None
    created_at: int
    updated_at: int


def _require_scope(tenant: str, user_id: str) -> None:
    if not tenant or not user_id:
        raise ValueError("記憶讀寫必須同時帶 tenant 與 user_id(預設拒絕跨 user 查詢)")


class MemoryStore:
    """per-user 記憶的 SQLite 後端。傳 ':memory:' 可作測試用記憶體 DB。"""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.db_path)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._con
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_entry (
                id             INTEGER PRIMARY KEY,
                tenant         TEXT NOT NULL,
                user_id        TEXT NOT NULL,
                kind           TEXT NOT NULL,
                content        TEXT NOT NULL,
                source_session TEXT,
                created_at     INTEGER NOT NULL,
                updated_at     INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mem_scope ON memory_entry(tenant, user_id, kind);

            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                content, content='memory_entry', content_rowid='id', tokenize='trigram'
            );

            CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memory_entry BEGIN
                INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memory_entry BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memory_entry BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content);
            END;
            """
        )
        c.commit()

    # -- 寫入 --
    def add(
        self,
        tenant: str,
        user_id: str,
        kind: str,
        content: str,
        source_session: str | None = None,
    ) -> int:
        _require_scope(tenant, user_id)
        if kind not in VALID_KINDS:
            raise ValueError(f"未知 kind: {kind!r}(可用:{sorted(VALID_KINDS)})")
        if not content.strip():
            raise ValueError("content 不可為空")
        now = int(time.time())
        cur = self._con.execute(
            "INSERT INTO memory_entry(tenant,user_id,kind,content,source_session,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (tenant, user_id, kind, content.strip(), source_session, now, now),
        )
        self._con.commit()
        return int(cur.lastrowid)

    # -- 查詢(一律 scope 在 tenant+user_id)--
    def list_for_user(
        self, tenant: str, user_id: str, kinds: list[str] | None = None, limit: int = 50
    ) -> list[MemoryEntry]:
        _require_scope(tenant, user_id)
        sql = "SELECT * FROM memory_entry WHERE tenant=? AND user_id=?"
        params: list = [tenant, user_id]
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params += kinds
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [self._row(r) for r in self._con.execute(sql, params)]

    def search(
        self,
        tenant: str,
        user_id: str,
        query: str,
        kinds: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemoryEntry]:
        """以 query 在該 user 的記憶中做全文檢索;短查詢或 FTS 失敗時退回 LIKE。"""
        _require_scope(tenant, user_id)
        q = query.strip()
        if not q:
            return self.list_for_user(tenant, user_id, kinds, limit)

        kind_clause = ""
        kind_params: list = []
        if kinds:
            kind_clause = f" AND e.kind IN ({','.join('?' * len(kinds))})"
            kind_params = list(kinds)

        # trigram 需要 >= 3 字元;以 phrase 包裹避免 FTS 查詢語法字元出錯
        if len(q) >= 3:
            try:
                fts_q = '"' + q.replace('"', '""') + '"'
                sql = (
                    "SELECT e.* FROM memory_entry e JOIN memory_fts f ON f.rowid=e.id "
                    "WHERE memory_fts MATCH ? AND e.tenant=? AND e.user_id=?"
                    + kind_clause
                    + " ORDER BY rank LIMIT ?"
                )
                params = [fts_q, tenant, user_id, *kind_params, limit]
                return [self._row(r) for r in self._con.execute(sql, params)]
            except sqlite3.OperationalError:
                pass  # 退回 LIKE

        sql = (
            "SELECT e.* FROM memory_entry e WHERE e.tenant=? AND e.user_id=? AND e.content LIKE ?"
            + kind_clause
            + " ORDER BY e.updated_at DESC LIMIT ?"
        )
        params = [tenant, user_id, f"%{q}%", *kind_params, limit]
        return [self._row(r) for r in self._con.execute(sql, params)]

    # -- 刪除(隱私/合規)--
    def forget(self, tenant: str, user_id: str) -> int:
        _require_scope(tenant, user_id)
        cur = self._con.execute(
            "DELETE FROM memory_entry WHERE tenant=? AND user_id=?", (tenant, user_id)
        )
        self._con.commit()
        return cur.rowcount

    def close(self) -> None:
        self._con.close()

    @staticmethod
    def _row(r: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=r["id"],
            tenant=r["tenant"],
            user_id=r["user_id"],
            kind=r["kind"],
            content=r["content"],
            source_session=r["source_session"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
