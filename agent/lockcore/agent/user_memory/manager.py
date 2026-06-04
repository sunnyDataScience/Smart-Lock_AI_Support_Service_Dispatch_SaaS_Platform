"""MemoryManager — nanobot 端協調者,接 turn 狀態機的 BUILD / SAVE。

- BUILD:`build_context_block(tenant, user_id, query)` → 注入 <memory> 區塊到系統提示。
- SAVE :`record_turn(tenant, user_id, ...)` → 寫回該客人記憶(對應 Hermes sync)。
"""

from __future__ import annotations

from .provider import MemoryProvider, SqliteMemoryProvider


class MemoryManager:
    def __init__(self, provider: MemoryProvider | None = None):
        self.provider = provider or SqliteMemoryProvider()

    def build_context_block(
        self, tenant: str, user_id: str, query: str, limit: int = 8
    ) -> str:
        """給 BUILD 用:回傳該客人相關記憶的 <memory> 區塊;無記憶則回空字串。"""
        entries = self.provider.prefetch(tenant, user_id, query, limit=limit)
        if not entries:
            return ""
        lines = "\n".join(f"- {e.content}" for e in entries)
        return f"<memory>\n{lines}\n</memory>"

    def record_turn(
        self,
        tenant: str,
        user_id: str,
        user_msg: str,
        assistant_msg: str = "",
        session_id: str | None = None,
    ) -> int:
        """給 SAVE 用(sync):把本輪寫回該客人記憶,回傳新增條目數。"""
        return self.provider.sync_turn(tenant, user_id, user_msg, assistant_msg, session_id)

    async def record_turn_async(
        self,
        tenant: str,
        user_id: str,
        user_msg: str,
        assistant_msg: str = "",
        session_id: str | None = None,
    ) -> int:
        """給 SAVE 用(async):兼容 sync 與 async(LLM)抽取器。"""
        return await self.provider.sync_turn_async(
            tenant, user_id, user_msg, assistant_msg, session_id
        )

    def forget(self, tenant: str, user_id: str) -> int:
        return self.provider.forget(tenant, user_id)
