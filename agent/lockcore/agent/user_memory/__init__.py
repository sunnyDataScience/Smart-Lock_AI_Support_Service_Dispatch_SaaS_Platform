"""⑤ 記憶層 — 以 tenant+user_id 為 key 的 per-user 記憶(移植 Hermes + 新寫隔離)。

Postgres 後端(PostgresMemoryStore / PostgresEscalationStore / PostgresMemoryProvider)
需 psycopg(optional dep `.[postgres]`),故**不在此頂層 eager import**,改由
`postgres_store` 子模組或 PostgresMemoryProvider 內 lazy import,讓 SQLite-only
安裝不必裝 psycopg。
"""

from .escalation import EscalationRecord, EscalationStore
from .llm_extractor import LLMExtractor
from .manager import MemoryManager
from .provider import MemoryProvider, SqliteMemoryProvider, default_extractor
from .store import MemoryEntry, MemoryStore

__all__ = [
    "MemoryManager",
    "MemoryProvider",
    "SqliteMemoryProvider",
    "default_extractor",
    "LLMExtractor",
    "MemoryEntry",
    "MemoryStore",
    "EscalationStore",
    "EscalationRecord",
]
