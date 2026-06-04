"""MemoryProvider — 可插拔記憶後端(沿用 Hermes memory_provider.py 精神,加 user_id 維度)。

PoC 提供 SqliteMemoryProvider;日後換 GCP NoSQL 只需新增一個 Provider,不動上層。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from .store import MemoryEntry, MemoryStore

# 抽取器:把一輪對話轉成若干 (kind, content) 記憶條目。
# PoC 預設只記下使用者訊息為 fact;日後可換成 LLM 抽取(memory-only 審查)。
Extractor = Callable[[str, str], list[tuple[str, str]]]


def default_extractor(user_msg: str, assistant_msg: str) -> list[tuple[str, str]]:
    user_msg = (user_msg or "").strip()
    if not user_msg:
        return []
    return [("fact", user_msg[:500])]


class MemoryProvider(ABC):
    @abstractmethod
    def prefetch(
        self, tenant: str, user_id: str, query: str, kinds: list[str] | None = None, limit: int = 8
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    def sync_turn(
        self,
        tenant: str,
        user_id: str,
        user_msg: str,
        assistant_msg: str,
        session_id: str | None = None,
    ) -> int: ...

    def forget(self, tenant: str, user_id: str) -> int:  # noqa: D102 (可選覆寫)
        return 0


class SqliteMemoryProvider(MemoryProvider):
    def __init__(self, db_path: str | Path = ":memory:", extractor: Extractor = default_extractor):
        self.store = MemoryStore(db_path)
        self.extractor = extractor

    def prefetch(self, tenant, user_id, query, kinds=None, limit=8) -> list[MemoryEntry]:
        # 先做相關性檢索;查不到(或整句 query 比不中)就退回該客人近期記憶 ——
        # 客人的已知事實本就該在 BUILD 注入,不該因 query 字面不合而漏掉。
        hits = self.store.search(tenant, user_id, query, kinds=kinds, limit=limit)
        if hits:
            return hits
        return self.store.list_for_user(tenant, user_id, kinds=kinds, limit=limit)

    def sync_turn(self, tenant, user_id, user_msg, assistant_msg, session_id=None) -> int:
        import inspect

        call = getattr(self.extractor, "__call__", self.extractor)
        if inspect.iscoroutinefunction(call):
            raise TypeError("sync_turn 不支援 async extractor,請改用 sync_turn_async")
        n = 0
        for kind, content in self.extractor(user_msg, assistant_msg):
            self.store.add(tenant, user_id, kind, content, source_session=session_id)
            n += 1
        return n

    async def sync_turn_async(self, tenant, user_id, user_msg, assistant_msg, session_id=None) -> int:
        """SAVE 用的 async 版:同時兼容 sync extractor 與 async(LLM)extractor。"""
        import inspect

        pairs = self.extractor(user_msg, assistant_msg)
        if inspect.isawaitable(pairs):
            pairs = await pairs
        n = 0
        for kind, content in pairs:
            self.store.add(tenant, user_id, kind, content, source_session=session_id)
            n += 1
        return n

    def forget(self, tenant, user_id) -> int:
        return self.store.forget(tenant, user_id)
