"""Postgres(psycopg3 sync)的 per-user 記憶 / escalation 後端。

與 store.py / escalation.py 的 SQLite 版**同介面、同 dataclass**(MemoryEntry /
EscalationRecord),讓上層 MemoryProvider 無感切換。

設計對齊:
- 核心不變量沿用:**所有讀寫都必須帶 `tenant + user_id`**(default deny),
  與 SQLite 版一致 —— 多用戶客服隔離的根基。
- 中文子字串檢索:SQLite 用 FTS5 trigram;Postgres 改 **pg_trgm + GIN**
  (見 SQL/migrations/033),用 ILIKE 命中、`similarity()` 排序。
- schema 固定 `agent.*`(與營運 saas.* / public.* 隔離,見 CR-0023 §8)。
- 連線:lazy connect + autocommit + 斷線透明重連(沿用 api/core/db.py 精神的 sync 版)。
"""

from __future__ import annotations

import json
import os
import time

import psycopg
from psycopg.rows import dict_row

from .escalation import EscalationRecord
from .store import VALID_KINDS, MemoryEntry

_SCHEMA = "agent"


def _require_scope(tenant: str, user_id: str) -> None:
    if not tenant or not user_id:
        raise ValueError("記憶讀寫必須同時帶 tenant 與 user_id(預設拒絕跨 user 查詢)")


class _PgConn:
    """共用的 lazy connect + 自動重連(autocommit)。sqlite 版用不到,故獨立於此。"""

    def __init__(self, uri: str):
        if not uri:
            raise ValueError("Postgres 後端需要連線字串(POSTGRES_URI 未設定)")
        self._uri = uri
        self._con: psycopg.Connection | None = None

    def conn(self) -> psycopg.Connection:
        c = self._con
        if c is not None and not c.closed and not getattr(c, "broken", False):
            return c
        if c is not None:
            try:
                c.close()
            except Exception:  # noqa: BLE001 — 重連前盡力關舊連線,失敗不致命
                pass
        self._con = psycopg.connect(self._uri, autocommit=True, row_factory=dict_row)
        return self._con

    def close(self) -> None:
        if self._con is not None:
            try:
                self._con.close()
            finally:
                self._con = None


class PostgresMemoryStore:
    """per-user 記憶的 Postgres 後端(agent.memory_entry)。"""

    def __init__(self, uri: str | None = None):
        self._db = _PgConn(uri or os.getenv("POSTGRES_URI", ""))

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
        cur = self._db.conn().execute(
            f"INSERT INTO {_SCHEMA}.memory_entry"
            "(tenant,user_id,kind,content,source_session,created_at,updated_at)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (tenant, user_id, kind, content.strip(), source_session, now, now),
        )
        return int(cur.fetchone()["id"])

    # -- 查詢(一律 scope 在 tenant+user_id)--
    def list_for_user(
        self, tenant: str, user_id: str, kinds: list[str] | None = None, limit: int = 50
    ) -> list[MemoryEntry]:
        _require_scope(tenant, user_id)
        sql = f"SELECT * FROM {_SCHEMA}.memory_entry WHERE tenant=%s AND user_id=%s"
        params: list = [tenant, user_id]
        if kinds:
            sql += " AND kind = ANY(%s)"
            params.append(list(kinds))
        sql += " ORDER BY updated_at DESC LIMIT %s"
        params.append(limit)
        return [self._row(r) for r in self._db.conn().execute(sql, params).fetchall()]

    def search(
        self,
        tenant: str,
        user_id: str,
        query: str,
        kinds: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemoryEntry]:
        """以 query 在該 user 的記憶中做子字串檢索(pg_trgm ILIKE + similarity 排序)。"""
        _require_scope(tenant, user_id)
        q = query.strip()
        if not q:
            return self.list_for_user(tenant, user_id, kinds, limit)

        sql = (
            f"SELECT * FROM {_SCHEMA}.memory_entry"
            " WHERE tenant=%s AND user_id=%s AND content ILIKE %s"
        )
        params: list = [tenant, user_id, f"%{q}%"]
        if kinds:
            sql += " AND kind = ANY(%s)"
            params.append(list(kinds))
        # similarity 由 pg_trgm 提供;命中相關度高者優先,同分以新近排序。
        sql += " ORDER BY similarity(content, %s) DESC, updated_at DESC LIMIT %s"
        params += [q, limit]
        return [self._row(r) for r in self._db.conn().execute(sql, params).fetchall()]

    # -- 刪除(隱私/合規)--
    def forget(self, tenant: str, user_id: str) -> int:
        _require_scope(tenant, user_id)
        cur = self._db.conn().execute(
            f"DELETE FROM {_SCHEMA}.memory_entry WHERE tenant=%s AND user_id=%s",
            (tenant, user_id),
        )
        return cur.rowcount

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _row(r: dict) -> MemoryEntry:
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


class PostgresEscalationStore:
    """轉真人 / 派工紀錄的 Postgres 後端(agent.escalation)。"""

    def __init__(self, uri: str | None = None):
        self._db = _PgConn(uri or os.getenv("POSTGRES_URI", ""))

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
        cur = self._db.conn().execute(
            f"INSERT INTO {_SCHEMA}.escalation"
            "(tenant,user_id,reason,is_explicit,facts_snapshot,created_at)"
            " VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                tenant,
                user_id,
                reason.strip(),
                is_explicit,
                json.dumps(facts_snapshot or {}, ensure_ascii=False),
                now,
            ),
        )
        return int(cur.fetchone()["id"])

    def list_for_user(self, tenant: str, user_id: str, limit: int = 50) -> list[EscalationRecord]:
        _require_scope(tenant, user_id)
        rows = self._db.conn().execute(
            f"SELECT * FROM {_SCHEMA}.escalation WHERE tenant=%s AND user_id=%s"
            " ORDER BY created_at DESC LIMIT %s",
            (tenant, user_id, limit),
        ).fetchall()
        return [self._row(r) for r in rows]

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _row(r: dict) -> EscalationRecord:
        snap = r["facts_snapshot"]
        # psycopg 對 JSONB 欄位直接回 dict;若為文字則 json.loads。
        if isinstance(snap, str):
            snap = json.loads(snap or "{}")
        return EscalationRecord(
            id=r["id"],
            tenant=r["tenant"],
            user_id=r["user_id"],
            reason=r["reason"],
            is_explicit=bool(r["is_explicit"]),
            facts_snapshot=snap or {},
            created_at=r["created_at"],
        )
